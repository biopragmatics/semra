"""This file contains the client for the Neo4j database."""

import os
import typing as t
from collections import Counter
from typing import Any, TypeAlias

import neo4j
import pydantic
from neo4j import Transaction, unit_of_work

import semra
from semra import Evidence, MappingSet, Reference

__all__ = [
    "Node",
    "Neo4jClient",
]

Node: TypeAlias = t.Mapping[str, Any]

TxResult: TypeAlias = list[list[Any]] | None

ReferenceHint: TypeAlias = str | Reference


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

        Parameters
        ----------
        uri :
            The URI of the Neo4j database.
        user :
            The username for the Neo4j database.
        password :
            The password for the Neo4j database.
        """
        self.driver = None
        uri = uri or os.environ.get("NEO4J_URL") or "bolt://0.0.0.0:7687"
        user = user or os.environ.get("NEO4J_USER")
        password = password or os.environ.get("NEO4J_PASSWORD")

        self.driver = neo4j.GraphDatabase.driver(uri=uri, auth=(user, password), max_connection_lifetime=180)

    def __del__(self):
        # Ensure driver is shut down when client is destroyed
        if self.driver is not None:
            self.driver.close()

    def read_query(self, query: str, **query_params) -> list[list]:
        """Run a read-only query

        Parameters
        ----------
        query :
            The cypher query to run
        query_params :
            The parameters to pass to the query

        Returns
        -------
        :
            The result of the query
        """
        with self.driver.session() as session:
            values = session.execute_read(do_cypher_tx, query, **query_params)

        return values

    def write_query(self, query: str, **query_params):
        """Run a write query.

        Parameters
        ----------
        query :
            The cypher query to run
        query_params :
            The parameters to pass to the query
        """
        with self.driver.session() as session:
            return session.write_transaction(do_cypher_tx, query, **query_params)

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
        """Get a mapping."""
        if not curie.startswith("semra.mapping:"):
            curie = f"semra.mapping:{curie}"
        query = """\
        MATCH
            (mapping {curie: $curie})-[:`owl:annotatedSource`]->(source) ,
            (mapping {curie: $curie})-[:`owl:annotatedTarget`]->(target) ,
            (mapping {curie: $curie})-[:hasEvidence]->(evidence)
        OPTIONAL MATCH
            (evidence)-[:fromSet]->(mset)
        OPTIONAL MATCH
            (evidence)-[:hasAuthor]->(author)
        RETURN mapping, source.curie, target.curie, collect([evidence, mset, author.curie])
        """
        mapping, source_curie, target_curie, evidence_pairs = self.read_query(query, curie=curie)[0]
        evidence = []
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
            evidence.append(pydantic.parse_obj_as(Evidence, evidence_dict))
        return semra.Mapping(
            s=Reference.from_curie(source_curie),
            p=Reference.from_curie(mapping["predicate"]),
            o=Reference.from_curie(target_curie),
            evidence=evidence,
        )

    def get_equivalent(self, curie: ReferenceHint) -> list[Reference]:
        """Get equivalent references."""

    def get_mapping_sets(self) -> list[MappingSet]:
        """Get all mappings sets."""
        query = "MATCH (m:mappingset) RETURN m"
        records = self.read_query(query)
        return [MappingSet.parse_obj(record) for record, in records]

    def get_mapping_set(self, curie: ReferenceHint) -> MappingSet:
        """Get a mappings set.

        :param curie: The CURIE for a mapping set, using ``semra.mappingset`` as a prefix.
            For example, use ``semra.mappingset:7831d5bc95698099fb6471667e5282cd`` for biomappings
        :return: A mapping set
        """
        if not curie.startswith("semra.mappingset:"):
            curie = f"semra.mappingset:{curie}"
        node = self._get_node_by_curie(curie)
        return MappingSet.parse_obj(node)

    def get_evidence(self, curie: str) -> Evidence:
        query = "MATCH (n {curie: $curie}) RETURN n"
        res = self.read_query(query, curie=curie)
        return res[0][0]

    def summarize_predicates(self) -> Counter:
        """Get a counter of predicates."""
        query = "MATCH (m:mapping) RETURN m.predicate, count(m.predicate)"
        return Counter(dict(self.read_query(query)))

    def summarize_justifications(self) -> Counter:
        """Get a counter of mapping justifications."""
        query = "MATCH (e:evidence) RETURN e.mapping_justification, count(e.mapping_justification)"
        return Counter({k.removeprefix("semapv:"): v for k, v in self.read_query(query)})

    def summarize_evidence_types(self) -> Counter:
        query = "MATCH (e:evidence) RETURN e.type, count(e.type)"
        return Counter(dict(self.read_query(query)))

    def summarize_mapping_sets(self) -> Counter:
        """Get the number of evidences in each mapping set."""
        query = "MATCH (e:evidence)-[:fromSet]->(s:mappingset) RETURN s.curie, count(e)"
        return Counter(dict(self.read_query(query)))

    def summarize_nodes(self) -> Counter:
        # TODO count number of "equivalence classes"
        query = """\
        MATCH (n:evidence)   WITH count(n) as count RETURN 'Evidences'    as label, count UNION ALL
        MATCH (n:concept)    WITH count(n) as count RETURN 'References'     as label, count UNION ALL
        MATCH (n:concept)    WHERE n.priority WITH count(n) as count RETURN 'Concepts'     as label, count UNION ALL
        MATCH (n:mapping)    WITH count(n) as count RETURN 'Mappings'     as label, count UNION ALL
        MATCH (n:mappingset) WITH count(n) as count RETURN 'Mapping Sets' as label, count
        """
        return Counter(dict(self.read_query(query)))


# Follows example here:
# https://neo4j.com/docs/python-manual/current/session-api/#python-driver-simple-transaction-fn
# and from the docstring of neo4j.Session.read_transaction
@unit_of_work()
def do_cypher_tx(tx: Transaction, query: str, **query_params) -> list[list]:
    result = tx.run(query, parameters=query_params)
    return [record.values() for record in result]
