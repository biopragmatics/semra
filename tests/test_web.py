"""Test the app."""

import unittest
from typing import Any, ClassVar, cast

import networkx as nx
from fastapi import FastAPI
from flask import Flask
from starlette.testclient import TestClient

import semra
from semra import (
    EXACT_MATCH,
    UNSPECIFIED_MAPPING,
    Evidence,
    Mapping,
    MappingSet,
    Reference,
    SimpleEvidence,
)
from semra.client import (
    AutocompletionResults,
    BaseClient,
    ExampleMapping,
    FullSummary,
    ReferenceHint,
    _safe_label_or_type,
)
from semra.wsgi import get_app
from tests.constants import TEST_CURIES, a1, a2, b1, b2

MS1 = MappingSet(
    name="Test Mapping Set",
)
E1 = SimpleEvidence(
    mapping_set=MS1,
    justification=UNSPECIFIED_MAPPING,
)
M1 = Mapping(subject=a1, predicate=EXACT_MATCH, object=b1, evidence=[E1])
M1_INV = Mapping(subject=b1, predicate=EXACT_MATCH, object=a1, evidence=[E1])
M2 = Mapping(subject=a2, predicate=EXACT_MATCH, object=b2, evidence=[E1])
TEST_MAPPINGS = [M1, M2]
E1_M1_REFERENCE = E1.get_reference(M1)
E1_M2_REFERENCE = E1.get_reference(M2)
NAMES = {c.curie: c.name for c in TEST_CURIES}


class MockClient(BaseClient):
    """A mock client."""

    def get_concept_name(self, curie: ReferenceHint) -> str | None:
        """Get a concept name."""
        return NAMES.get(curie)  # type:ignore

    def get_exact_matches(
        self, curie: ReferenceHint, *, max_distance: int | None = None
    ) -> dict[Reference, str] | None:
        """Get exact matches for a given CURIE."""
        if curie == a1.curie:
            return {b1: cast(str, b1.name)}
        return None

    def get_evidence(self, curie: ReferenceHint) -> Evidence | None:
        """Get an evidence."""
        if curie == E1_M1_REFERENCE.curie:
            return E1
        return None

    def get_mapping_set(self, curie: ReferenceHint) -> MappingSet | None:
        """Get a mapping set."""
        if curie == MS1.curie:
            return MS1
        return None

    def get_mapping_sets(self) -> list[MappingSet]:
        """Get all mapping sets."""
        return [MS1]

    def get_mapping(self, curie: ReferenceHint) -> semra.Mapping | None:
        """Get a mapping."""
        if curie == M1.curie:
            return M1
        elif curie == M2.curie:
            return M2
        return None

    def sample_mappings_from_set(self, curie: ReferenceHint, n: int = 10) -> list[ExampleMapping]:
        """Get example mappings from a set."""
        if curie == MS1.curie:
            return [ExampleMapping.from_mapping(M1)]
        raise KeyError

    def get_full_summary(self) -> FullSummary:
        """Get an empty summary."""
        return FullSummary()

    def get_connected_component_graph(
        self, curie: ReferenceHint, relation_constraint: str | None = None
    ) -> nx.MultiDiGraph | None:
        """Get a networkx MultiDiGraph representing the connected component of mappings around the given CURIE.

        :param curie: A CURIE string or reference
        :param relation_constraint: Relation type constraints (separated by |)
            to apply when considering relations in the connected component.
            If None, defaults to the relations defined in the client.

        :returns: A networkx MultiDiGraph where mappings subject CURIE strings are th
        """
        if curie != a1.curie:
            return None

        # TODO unify with mapping graph!

        g = nx.MultiDiGraph()
        g.add_node(a1.curie)  # what about other parts?
        g.add_node(b1.curie)
        g.add_edge(a1.curie, b1.curie, key=M1.curie, type=EXACT_MATCH.curie)
        g.add_edge(b1.curie, a1.curie, key=M1_INV.curie, type=EXACT_MATCH.curie)
        return g

    def initialize_autocomplete(self) -> None:
        """Mock initializing autocomplete."""

    def get_autocompletion(self, prefix: str, *, top_n: int = 100) -> AutocompletionResults:
        """Mock getting an autocompletion."""
        raise NotImplementedError(f"need mock for {prefix}")

    def read_query(self, query: str, **query_params: Any) -> list[list[Any]]:
        """Mock read query."""
        if "MATCH (n:concept) WHERE n.name IS NOT NULL RETURN n.name, n.curie LIMIT 1" in query:
            return [[a1.name, a1.curie]]
        elif "MATCH (n:concept) RETURN n.curie LIMIT 1" in query:
            return [[a1.curie]]
        raise NotImplementedError(f"Query not implemented: {query}")


class BaseTest(unittest.TestCase):
    """Test the app."""

    dao: ClassVar[BaseClient]
    flask_app: ClassVar[Flask]
    fastapi_app: ClassVar[FastAPI]

    @classmethod
    def setUpClass(cls) -> None:
        """Set up the class with a mock client and app."""
        cls.dao = MockClient()
        cls.flask_app, cls.fastapi_app = get_app(
            client=cls.dao, return_flask=True, use_biomappings=False
        )


class TestFrontend(BaseTest):
    """Test the app."""

    def test_home(self) -> None:
        """Test the homepage."""
        with self.flask_app.test_client() as client:
            res = client.get("/")
            self.assertEqual(200, res.status_code, msg=res.text)

    def test_mapping(self) -> None:
        """Test the mapping page."""
        with self.flask_app.test_client() as client:
            res = client.get(f"/mapping/{M1.curie}")
            self.assertEqual(200, res.status_code, msg=res.text)

    def test_mapping_set(self) -> None:
        """Test the mapping set page."""
        with self.flask_app.test_client() as client:
            res = client.get(f"/mapping_set/{MS1.curie}")
            self.assertEqual(200, res.status_code, msg=res.text)

    def test_concept(self) -> None:
        """Test the mapping set page."""
        with self.flask_app.test_client() as client:
            res = client.get(f"/concept/{a1.curie}")
            self.assertEqual(200, res.status_code, msg=res.text)


class TestAPI(BaseTest):
    """Test the app."""

    test_client: ClassVar[TestClient]

    @classmethod
    def setUpClass(cls) -> None:
        """Set up the class with a mock client and app."""
        super().setUpClass()
        cls.test_client = TestClient(cls.fastapi_app)

    def test_evidence(self) -> None:
        """Test the evidence API."""
        res = self.test_client.get(f"/api/evidence/{E1_M1_REFERENCE.curie}")
        self.assertEqual(200, res.status_code)
        self.assertEqual(E1, SimpleEvidence.model_validate(res.json()))

        res_not_found = self.test_client.get(f"/api/evidence/{E1_M2_REFERENCE.curie}")
        self.assertEqual(404, res_not_found.status_code)

    def test_mapping_set(self) -> None:
        """Test the mapping set API."""
        res = self.test_client.get(f"/api/mapping_set/{MS1.curie}")
        self.assertEqual(200, res.status_code)
        self.assertEqual(MS1, MappingSet.model_validate(res.json()))

        res_not_found = self.test_client.get("/api/mapping_set/abcdef")
        self.assertEqual(404, res_not_found.status_code)

        res_all = self.test_client.get("/api/mapping_set/")
        self.assertEqual(200, res_all.status_code)
        self.assertEqual([MS1], [MappingSet.model_validate(r) for r in res_all.json()])

    def test_mapping(self) -> None:
        """Test the mapping API."""
        res = self.test_client.get(f"/api/mapping/{M1.curie}")
        self.assertEqual(200, res.status_code)
        self.assertEqual(M1, Mapping.model_validate(res.json()))

        res_not_found = self.test_client.get("/api/mapping/abcdef")
        self.assertEqual(404, res_not_found.status_code)

    def test_exact_matches(self) -> None:
        """Test the exact matches API."""
        res = self.test_client.get(f"/api/exact/{a1.curie}")
        self.assertEqual(200, res.status_code)
        records = res.json()
        self.assertEqual(
            [b1], [Reference.model_validate(r) for r in records], msg=f"Results: {records}"
        )

        res_not_found = self.test_client.get("/api/exact/abcdef")
        self.assertEqual(404, res_not_found.status_code)

    def test_component(self) -> None:
        """Test the connected components API."""
        res = self.test_client.get(f"/api/cytoscape/{a1.curie}")
        self.assertEqual(200, res.status_code)
        res.json()

        res_not_found = self.test_client.get("/api/cytoscape/abcdef")
        self.assertEqual(404, res_not_found.status_code)


class TestSafeLabelType(BaseTest):
    """Test the autocompletion API."""

    def test_safe_label_type(self) -> None:
        """Test the _safe_label_or_type function."""
        self.assertEqual("a1", _safe_label_or_type("a1"))
        self.assertEqual("`a:1`", _safe_label_or_type("a:1"))
        self.assertEqual("`b.c:2`", _safe_label_or_type("b.c:2"))
        self.assertEqual(f"`{EXACT_MATCH.curie}`", _safe_label_or_type(EXACT_MATCH.curie))
