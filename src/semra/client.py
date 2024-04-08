"""This file contains the client for the Neo4j database."""

from __future__ import annotations

import os
import typing as t
from collections import Counter
from typing import Any

import bioregistry
import neo4j
import neo4j.graph
import networkx as nx
import pydantic
from neo4j import unit_of_work
from typing_extensions import TypeAlias

import semra
from semra import Evidence, MappingSet, Reference
from semra.io import _get_name_by_curie
from semra.rules import RELATIONS

__all__ = [
    "Node",
    "Neo4jClient",
]

Node: TypeAlias = t.Mapping[str, Any]

TxResult: TypeAlias = t.Optional[t.List[t.List[Any]]]

ReferenceHint: TypeAlias = t.Union[str, Reference]


def _safe_curie(curie_or_luid: ReferenceHint, prefix: str) -> str:
    if isinstance(curie_or_luid, Reference):
        return curie_or_luid.curie
    if curie_or_luid.startswith(prefix):
        return curie_or_luid
    return f"{prefix}:{curie_or_luid}"


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

        self.driver = neo4j.GraphDatabase.driver(uri=uri, auth=(user, password), max_connection_lifetime=180)

        query = "CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType"
        self._all_relations = {x for x, in self.read_query(query)}
        self._rel_q = "|".join(f"`{x.curie}`" for x in RELATIONS if x.curie in self._all_relations)

    def __del__(self):
        """Ensure driver is shut down when client is destroyed."""
        if self.driver is not None:
            self.driver.close()

    def read_query(self, query: str, **query_params) -> list[list]:
        """Run a read-only query.

        :param query: The cypher query to run
        :param query_params: The parameters to pass to the query
        :return: The result of the query
        """
        with self.driver.session() as session:
            values = session.execute_read(_do_cypher_tx, query, **query_params)

        return values

    def write_query(self, query: str, **query_params):
        """Run a write query.

        :param query: The cypher query to run
        :param query_params: The parameters to pass to the query
        :return: The result of the write query
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

    def _get_node_by_curie(self, curie: ReferenceHint) -> Node:
        if isinstance(curie, Reference):
            curie = curie.curie
        query = "MATCH (n {curie: $curie}) RETURN n"
        res = self.read_query(query, curie=curie)
        return res[0][0]

    def get_mapping(self, curie: ReferenceHint) -> semra.Mapping:
        """Get a mapping.

        :param curie: Either a Reference object, a string representing
            a curie with ``semra.mapping`` as the prefix, or a local
            unique identifier representing a SeMRA mapping.
        :return: A semantic mapping object
        """
        curie = _safe_curie(curie, "semra.mapping")
        query = """\
        MATCH
            (mapping {curie: $curie}) ,
            (mapping)-[:`owl:annotatedSource`]->(source) ,
            (mapping)-[:`owl:annotatedTarget`]->(target) ,
            (mapping)-[:hasEvidence]->(evidence)
        OPTIONAL MATCH
            (evidence)-[:fromSet]->(mset)
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
                evidence_dict["mapping_set"] = MappingSet.parse_obj(mapping_set_node)
            if author_curie:
                evidence_dict["author"] = Reference.from_curie(author_curie)
            evidence_dict["evidence_type"] = evidence_dict.pop("type")
            if evidence_dict["evidence_type"] == "reasoned":
                evidence_dict["mappings"] = []  # TODO add in mappings?
            evidence_dict["justification"] = Reference.from_curie(evidence_dict.pop("mapping_justification"))
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
        return [MappingSet.parse_obj(record) for record, in records]

    def get_mapping_set(self, curie: ReferenceHint) -> MappingSet:
        """Get a mappings set.

        :param curie: The CURIE for a mapping set, using ``semra.mappingset`` as a prefix.
            For example, use ``semra.mappingset:7831d5bc95698099fb6471667e5282cd`` for biomappings
        :return: A mapping set object
        """
        curie = _safe_curie(curie, "semra.mappingset")
        node = self._get_node_by_curie(curie)
        return MappingSet.parse_obj(node)

    def get_evidence(self, curie: ReferenceHint) -> Evidence:
        """Get an evidence.

        :param curie: The CURIE for a mapping set, using ``semra.evidence`` as a prefix.
        :return: An evidence object
        """
        curie = _safe_curie(curie, "semra.evidence")
        query = "MATCH (n {curie: $curie}) RETURN n"
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
            {(prefix, t.cast(str, bioregistry.get_name(prefix))): count for prefix, count in self.read_query(query)}
        )

    def summarize_authors(self) -> t.Counter[tuple[str, str]]:
        """Get a counter of the number of evidences each author has contributed to."""
        query = "MATCH (e:evidence)-[:hasAuthor]->(a:concept) RETURN a.curie, a.name, count(e)"
        return self._count_with_name(query)

    def get_highest_exact_matches(self, limit: int = 10) -> t.Counter[tuple[str, str]]:
        """Get a counter of concepts with the highest exact matches.

        :param limit: The number of top concepts to return
        :return: A counter with keys that are CURIE/name pairs
        """
        query = """\
            MATCH (a)-[:`skos:exactMatch`]-(b)
            WHERE a.priority
            RETURN a.curie, a.name, count(distinct b) as c
            ORDER BY c DESCENDING
            LIMIT $limit
        """
        return self._count_with_name(query, limit=limit)

    def _count_with_name(self, query: str, **kwargs: Any) -> t.Counter[tuple[str, str]]:
        return Counter({(curie, name): count for curie, name, count in self.read_query(query, **kwargs)})

    def get_exact_matches(self, curie: ReferenceHint, *, max_distance: int = 7) -> dict[Reference, str]:
        """Get a mapping of references->name for all concepts equivalent to the given concept."""
        if isinstance(curie, Reference):
            curie = curie.curie
        query = f"""\
            MATCH (a {{curie: $curie}})-[:`skos:exactMatch`*1..{max_distance}]-(b)
            WHERE a.curie <> b.curie
            RETURN b.curie, b.name
        """
        return {Reference.from_curie(n_curie): name for n_curie, name in self.read_query(query, curie=curie)}

    def get_connected_component(
        self, curie: ReferenceHint, max_distance: int = 7
    ) -> tuple[list[neo4j.graph.Node], list[neo4j.graph.Relationship]]:
        """Get the nodes and relations in the connected component of mappings around the given CURIE.

        :param curie: A CURIE string or reference
        :param max_distance: The maximum number of hops to consider
        :return: A pair of:

            1. The nodes in the connected component, as Neo4j node objects
            2. The relationships in the connected component, as Neo4j relationship objects
        """
        if isinstance(curie, Reference):
            curie = curie.curie
        query = f"""\
            MATCH (:concept {{curie: $curie}})-[r:{self._rel_q} *..{max_distance}]-(n:concept)
            WHERE ALL(p IN r WHERE p.primary or p.secondary)
            RETURN collect(DISTINCT n) AS nodes, collect(DISTINCT r) AS relations
        """
        res = self.read_query(query, curie=curie)
        nodes = res[0][0]
        relations = sorted({r for relations in res[0][1] for r in relations}, key=lambda r: r.type)
        return nodes, relations

    def get_connected_component_graph(self, curie: ReferenceHint) -> nx.MultiDiGraph:
        """Get a networkx MultiDiGraph representing the connected component of mappings around the given CURIE.

        :param curie: A CURIE string or reference
        :returns: A networkx MultiDiGraph where mappings subject CURIE strings are th
        """
        nodes, relations = self.get_connected_component(curie)
        g = nx.MultiDiGraph()
        for node in nodes:
            g.add_node(node["curie"], **node)
        for relation in relations:
            g.add_edge(
                relation.nodes[0]["curie"],  # type: ignore
                relation.nodes[1]["curie"],  # type: ignore
                key=relation.element_id,
                type=relation.type,
                **relation,
            )
        return g

    def get_concept_name(self, curie: ReferenceHint) -> str | None:
        """Get the name for a CURIE or reference."""
        if isinstance(curie, Reference):
            curie = curie.curie
        return _get_name_by_curie(curie)

    def sample_mappings_from_set(self, curie: ReferenceHint, n: int = 10) -> t.List:
        """Get n mappings from a given set (by CURIE)."""
        if isinstance(curie, Reference):
            curie = curie.curie
        query = f"""\
        MATCH
            (:mappingset {{curie: $curie}})<-[:fromSet]-()<-[:hasEvidence]-(n:mapping)
        MATCH
            (n)-[:`owl:annotatedSource`]->(s)
        MATCH
            (n)-[:`owl:annotatedTarget`]->(t)
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
