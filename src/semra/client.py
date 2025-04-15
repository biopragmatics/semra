"""This file contains the client for the Neo4j database."""

from __future__ import annotations

import os
import typing as t
from collections import Counter
from typing import Any, TypeAlias, cast

import bioregistry
import neo4j
import neo4j.graph
import networkx as nx
import pydantic
from neo4j import unit_of_work

import semra
from semra import Evidence, MappingSet, Reference
from semra.rules import (
    RELATIONS,
    SEMRA_EVIDENCE_PREFIX,
    SEMRA_MAPPING_PREFIX,
    SEMRA_MAPPING_SET_PREFIX,
)

__all__ = [
    "Neo4jClient",
    "Node",
]

Node: TypeAlias = t.Mapping[str, Any]

TxResult: TypeAlias = list[list[Any]] | None

ReferenceHint: TypeAlias = str | Reference

DEFAULT_MAX_LENGTH = 3


def _safe_curie(curie_or_luid: ReferenceHint, prefix: str) -> str:
    if isinstance(curie_or_luid, Reference):
        return curie_or_luid.curie
    if curie_or_luid.startswith(prefix):
        return curie_or_luid
    return f"{prefix}:{curie_or_luid}"


#: A cypher query that gets all of the databases' relation types
RELATIONS_CYPHER = "CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType"

#: A cypher query format string for getting the name of a concept
CONCEPT_NAME_CYPHER = "MATCH (n:concept) WHERE n.curie = $curie RETURN n.name LIMIT 1"


class Neo4jClient:
    """A client to Neo4j."""

    _session: neo4j.Session | None = None

    def __init__(
        self,
        uri: str | None = None,
        user: str | None = None,
        password: str | None = None,
    ):
        """Initialize the client.

        :param uri: The URI of the Neo4j database.
        :param user: The username for the Neo4j database.
        :param password: The password for the Neo4j database.
        """
        uri = uri or os.environ.get("NEO4J_URL") or "bolt://0.0.0.0:7687"
        user = user or os.environ.get("NEO4J_USER")
        password = password or os.environ.get("NEO4J_PASSWORD")

        self.driver = neo4j.GraphDatabase.driver(
            uri=uri, auth=(user, password), max_connection_lifetime=180
        )

        self._all_relations = {curie for (curie,) in self.read_query(RELATIONS_CYPHER)}
        self._rel_q = "|".join(
            f"`{reference.curie}`"
            for reference in RELATIONS
            if reference.curie in self._all_relations
        )

    def __del__(self):
        """Ensure driver is shut down when client is destroyed."""
        if self.driver is not None:
            self.driver.close()

    def read_query(self, query: str, **query_params) -> list[list]:
        """Run a read-only query.

        :param query: The cypher query to run
        :param query_params: The parameters to pass to the query

        :returns: The result of the query
        """
        with self.driver.session() as session:
            values = session.execute_read(_do_cypher_tx, query, **query_params)

        return values

    def write_query(self, query: str, **query_params):
        """Run a write query.

        :param query: The cypher query to run
        :param query_params: The parameters to pass to the query

        :returns: The result of the write query
        """
        with self.driver.session() as session:
            return session.write_transaction(_do_cypher_tx, query, **query_params)

    def create_single_property_node_index(
        self, index_name: str, label: str, property_name: str, *, exist_ok: bool = False
    ) -> None:
        """Create a single-property node index.

        :param index_name: The name of the index to create.
        :param label: The label of the nodes to index.
        :param property_name: The node property to index.
        :param exist_ok: If True, do not raise an exception if the index already exists.
        """
        if_not = " IF NOT EXISTS" if exist_ok else ""
        if "." in label:
            label = f"`{label}`"
        if "." in index_name:
            index_name = index_name.replace(".", "_")
        query = f"CREATE INDEX {index_name}{if_not} FOR (n:{label}) ON (n.{property_name})"

        self.write_query(query)

    def _get_node_by_curie(self, curie: ReferenceHint, node_type: str | None = None) -> Node:
        if isinstance(curie, Reference):
            curie = curie.curie
        query = "MATCH (n%s {curie: $curie}) RETURN n" % (":" + node_type if node_type else "")
        res = self.read_query(query, curie=curie)
        return res[0][0]

    def get_mapping(self, curie: ReferenceHint) -> semra.Mapping:
        """Get a mapping.

        :param curie: Either a Reference object, a string representing a curie with
            ``semra.mapping`` as the prefix, or a local unique identifier representing a
            SeMRA mapping.

        :returns: A semantic mapping object
        """
        curie = _safe_curie(curie, SEMRA_MAPPING_PREFIX)
        query = """\
        MATCH
            (mapping:mapping {curie: $curie}) ,
            (mapping)-[:`owl:annotatedSource`]->(source:concept) ,
            (mapping)-[:`owl:annotatedTarget`]->(target:concept) ,
            (mapping)-[:hasEvidence]->(evidence:evidence)
        OPTIONAL MATCH
            (evidence)-[:fromSet]->(mset:mappingset)
        OPTIONAL MATCH
            (evidence)-[:hasAuthor]->(author)
        RETURN mapping, source.curie, target.curie, collect([evidence, mset, author.curie])
        LIMIT 1
        """
        mapping, source_curie, target_curie, evidence_pairs = self.read_query(query, curie=curie)[0]
        evidence: list[Evidence] = []
        for evidence_node, mapping_set_node, author_curie in evidence_pairs:
            evidence_dict = dict(evidence_node)
            if mapping_set_node:
                evidence_dict["mapping_set"] = MappingSet.model_validate(mapping_set_node)
            if author_curie:
                evidence_dict["author"] = Reference.from_curie(author_curie)
            evidence_dict["evidence_type"] = evidence_dict.pop("type")
            if evidence_dict["evidence_type"] == "reasoned":
                evidence_dict["mappings"] = []  # TODO add in mappings?
            evidence_dict["justification"] = Reference.from_curie(
                evidence_dict.pop("mapping_justification")
            )
            evidence.append(pydantic.parse_obj_as(Evidence, evidence_dict))  # type:ignore
        return semra.Mapping(
            s=Reference.from_curie(source_curie),
            p=Reference.from_curie(mapping["predicate"]),
            o=Reference.from_curie(target_curie),
            evidence=evidence,
        )

    def get_equivalent(self, curie: ReferenceHint) -> list[Reference]:
        """Get equivalent references."""
        raise NotImplementedError

    def get_mapping_sets(self) -> list[MappingSet]:
        """Get all mappings sets."""
        query = "MATCH (m:mappingset) RETURN m"
        records = self.read_query(query)
        return [MappingSet.model_validate(record) for (record,) in records]

    def get_mapping_set(self, curie: ReferenceHint) -> MappingSet:
        """Get a mappings set.

        :param curie: The CURIE for a mapping set, using ``semra.mappingset`` as a
            prefix. For example, use
            ``semra.mappingset:7831d5bc95698099fb6471667e5282cd`` for biomappings

        :returns: A mapping set object
        """
        curie = _safe_curie(curie, SEMRA_MAPPING_SET_PREFIX)
        node = self._get_node_by_curie(curie, "mappingset")
        return MappingSet.model_validate(node)

    def get_evidence(self, curie: ReferenceHint) -> Evidence:
        """Get an evidence.

        :param curie: The CURIE for a mapping set, using ``semra.evidence`` as a prefix.

        :returns: An evidence object
        """
        curie = _safe_curie(curie, SEMRA_EVIDENCE_PREFIX)
        query = "MATCH (n:evidence {curie: $curie}) RETURN n"
        res = self.read_query(query, curie=curie)
        return res[0][0]

    def summarize_predicates(self) -> t.Counter[str]:
        """Get a counter of predicates."""
        query = "MATCH (m:mapping) RETURN m.predicate, count(m.predicate)"
        return Counter(dict(self.read_query(query)))

    def summarize_justifications(self) -> t.Counter[str]:
        """Get a counter of mapping justifications."""
        query = "MATCH (e:evidence) RETURN e.mapping_justification, count(e.mapping_justification)"
        return Counter({k.removeprefix("semapv:"): v for k, v in self.read_query(query)})

    def summarize_evidence_types(self) -> t.Counter[str]:
        """Get a counter of evidence types."""
        query = "MATCH (e:evidence) RETURN e.type, count(e.type)"
        return Counter(dict(self.read_query(query)))

    def summarize_mapping_sets(self) -> t.Counter[str]:
        """Get the number of evidences in each mapping set."""
        query = "MATCH (e:evidence)-[:fromSet]->(s:mappingset) RETURN s.curie, count(e)"
        return Counter(dict(self.read_query(query)))

    def summarize_nodes(self) -> t.Counter[str]:
        """Get a counter of node types (concepts, evidences, mappings, mapping sets)."""
        query = """\
        MATCH (n:evidence)   WITH count(n) as count RETURN 'Evidences'    as label, count UNION ALL
        MATCH (n:concept)    WITH count(n) as count RETURN 'Concepts'     as label, count UNION ALL
        MATCH (n:concept)    WHERE n.priority WITH count(n) as count RETURN 'Equivalence Classes' \
as label, count UNION ALL
        MATCH (n:mapping)    WITH count(n) as count RETURN 'Mappings'     as label, count UNION ALL
        MATCH (n:mappingset) WITH count(n) as count RETURN 'Mapping Sets' as label, count
        """
        return Counter(dict(self.read_query(query)))

    def summarize_concepts(self) -> t.Counter[tuple[str, str]]:
        """Get a counter of prefixes in concept nodes."""
        query = "MATCH (e:concept) WHERE e.prefix <> 'orcid' RETURN e.prefix, count(e.prefix)"
        return Counter(
            {
                (prefix, t.cast(str, bioregistry.get_name(prefix))): count
                for prefix, count in self.read_query(query)
            }
        )

    def summarize_authors(self) -> t.Counter[tuple[str, str]]:
        """Get a counter of the number of evidences each author has contributed to."""
        query = "MATCH (e:evidence)-[:hasAuthor]->(a:concept) RETURN a.curie, a.name, count(e)"
        return self._count_with_name(query)

    def get_highest_exact_matches(self, limit: int = 10) -> t.Counter[tuple[str, str]]:
        """Get a counter of concepts with the highest exact matches.

        :param limit: The number of top concepts to return

        :returns: A counter with keys that are CURIE/name pairs
        """
        query = """\
            MATCH (a:concept)-[:`skos:exactMatch`]-(b:concept)
            WHERE a.priority
            RETURN a.curie, a.name, count(distinct b) as c
            ORDER BY c DESCENDING
            LIMIT $limit
        """
        return self._count_with_name(query, limit=limit)

    def _count_with_name(self, query: str, **kwargs: Any) -> t.Counter[tuple[str, str]]:
        return Counter(
            {(curie, name): count for curie, name, count in self.read_query(query, **kwargs)}
        )

    def get_exact_matches(
        self, curie: ReferenceHint, *, max_distance: int | None = None
    ) -> dict[Reference, str]:
        """Get a mapping of references->name for all concepts equivalent to the given concept."""
        if isinstance(curie, Reference):
            curie = curie.curie
        if max_distance is None:
            max_distance = DEFAULT_MAX_LENGTH
        query = f"""\
            MATCH (a:concept {{curie: $curie}})-[:`skos:exactMatch`*1..{max_distance}]-(b:concept)
            WHERE a.curie <> b.curie
            RETURN b.curie, b.name
        """
        return {
            cast(Reference, Reference.from_curie(n_curie)): name
            for n_curie, name in self.read_query(query, curie=curie)
        }

    def get_connected_component(
        self, curie: ReferenceHint, max_distance: int | None = None
    ) -> tuple[list[neo4j.graph.Node], list[neo4j.graph.Path]]:
        """Get the nodes and relations in the connected component of mappings around the given CURIE.

        :param curie: A CURIE string or reference
        :param max_distance: The maximum number of hops to consider

        :returns: A pair of:

            1. The nodes in the connected component, as Neo4j node objects
            2. The relationships in the connected component, as Neo4j relationship
               objects
        """
        if isinstance(curie, Reference):
            curie = curie.curie
        if max_distance is None:
            max_distance = DEFAULT_MAX_LENGTH

        connected_query = f"""\
            MATCH (:concept {{curie: $curie}})-[r:{self._rel_q} *..{max_distance}]-(n:concept)
            WHERE ALL(p IN r WHERE p.primary or p.secondary)
            RETURN DISTINCT n
            UNION ALL
            MATCH (n:concept {{curie: $curie}})
            RETURN n
        """
        nodes = [n[0] for n in self.read_query(connected_query, curie=curie)]

        component_curies = {node["curie"] for node in nodes}
        # component_curies.add(curie)

        edge_query = """\
            MATCH p=(a:concept)-[r]->(b:concept)
            WHERE a.curie in $curies and b.curie in $curies and (r.primary or r.secondary)
            RETURN p
        """
        relations = [r[0] for r in self.read_query(edge_query, curies=sorted(component_curies))]
        return nodes, relations

    def get_connected_component_graph(self, curie: ReferenceHint) -> nx.MultiDiGraph:
        """Get a networkx MultiDiGraph representing the connected component of mappings around the given CURIE.

        :param curie: A CURIE string or reference

        :returns: A networkx MultiDiGraph where mappings subject CURIE strings are th
        """
        nodes, paths = self.get_connected_component(curie)
        g = nx.MultiDiGraph()
        for node in nodes:
            g.add_node(node["curie"], **node)
        for path in paths:
            for relationship in path.relationships:
                g.add_edge(
                    path.start_node["curie"],  # type: ignore
                    path.end_node["curie"],  # type: ignore
                    key=relationship.id,
                    type=relationship.type,
                )
        return g

    def get_concept_name(self, curie: ReferenceHint) -> str | None:
        """Get the name for a CURIE or reference."""
        if isinstance(curie, Reference):
            curie = curie.curie
        try:
            name = self.read_query(CONCEPT_NAME_CYPHER, curie=curie)[0][0]
        except Exception:
            return None
        else:
            return name

    def sample_mappings_from_set(self, curie: ReferenceHint, n: int = 10) -> list:
        """Get n mappings from a given set (by CURIE)."""
        if isinstance(curie, Reference):
            curie = curie.curie
        query = f"""\
        MATCH
            (:mappingset {{curie: $curie}})<-[:fromSet]-(:evidence)<-[:hasEvidence]-(n:mapping)
        MATCH
            (n)-[:`owl:annotatedSource`]->(s:concept)
        MATCH
            (n)-[:`owl:annotatedTarget`]->(t:concept)
        WHERE s.name IS NOT NULL and t.name IS NOT NULL and s.curie < t.curie
        RETURN n.curie, n.predicate, s.curie, s.name, t.curie, t.name
        LIMIT {n}
        """
        return list(self.read_query(query, curie=curie))


# Follows example here:
# https://neo4j.com/docs/python-manual/current/session-api/#python-driver-simple-transaction-fn
# and from the docstring of neo4j.Session.read_transaction
@unit_of_work()
def _do_cypher_tx(tx, query, **query_params) -> list[list]:
    result = tx.run(query, parameters=query_params)
    return [record.values() for record in result]
