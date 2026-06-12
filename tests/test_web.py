"""Test the app."""

import unittest
from typing import ClassVar, cast

import networkx as nx
from bioregistry import NormalizedNamableReference
from fastapi import FastAPI
from flask import Flask
from sssom_pydantic import SemanticMapping
from starlette.testclient import TestClient

import semra
from semra import (
    EXACT_MATCH,
    Evidence,
    Mapping,
    MappingSet,
    Reference,
    SimpleEvidence,
)
from semra.client import (
    AutocompletionResults,
    BaseClient,
    FullSummary,
    ReferenceHint,
    _safe_label_or_type,
)
from semra.wsgi import get_app
from tests.constants import R1, R2, R3, R4, TEST_CURIES, TEST_MAPPING_SET

M1 = Mapping.from_sssom_pydantic(SemanticMapping.exact(R2, R1), TEST_MAPPING_SET)
M1_INV = Mapping.from_sssom_pydantic(SemanticMapping.exact(R1, R2), TEST_MAPPING_SET)
M2 = Mapping.from_sssom_pydantic(SemanticMapping.exact(R4, R3), TEST_MAPPING_SET)
TEST_MAPPINGS = [M1, M2]
E1_M1_REFERENCE = M1.evidence[0].get_reference(M1)
E1_M2_REFERENCE = M2.evidence[0].get_reference(M2)
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
        if curie == R2.curie:
            return {R1: cast(str, R1.name)}
        return None

    def get_evidence(self, curie: ReferenceHint) -> Evidence | None:
        """Get an evidence."""
        if curie == E1_M1_REFERENCE.curie:
            return M1.evidence[0]
        return None

    def get_mapping_set(self, uri: str) -> MappingSet | None:
        """Get a mapping set."""
        if uri == str(TEST_MAPPING_SET.id):
            return TEST_MAPPING_SET
        return None

    def get_mapping_sets(self) -> list[MappingSet]:
        """Get all mapping sets."""
        return [TEST_MAPPING_SET]

    def get_mapping(self, curie: ReferenceHint) -> semra.Mapping | None:
        """Get a mapping."""
        if curie == M1.curie:
            return M1
        elif curie == M2.curie:
            return M2
        return None

    def get_mappings_by_set(self, uri: str, n: int = 10) -> list[Mapping]:
        """Get example mappings from a set."""
        if uri == str(TEST_MAPPING_SET.id):
            return [M1]
        raise KeyError

    def get_full_summary(self) -> FullSummary:
        """Get an empty summary."""
        return FullSummary()

    def get_connected_component_graph(
        self, curie: ReferenceHint, relation_constraint: str | None = None
    ) -> nx.MultiDiGraph | None:
        """Get a networkx MultiDiGraph representing the connected component of mappings around the given CURIE.

        :param curie: A CURIE string or reference
        :param relation_constraint: Relation type constraints (separated by a pipe) to
            apply when considering relations in the connected component. If None,
            defaults to the relations defined in the client.

        :returns: A networkx MultiDiGraph where mappings subject CURIE strings are th
        """
        if curie != R2.curie:
            return None

        # TODO unify with mapping graph!

        g = nx.MultiDiGraph()
        g.add_node(R2.curie)  # what about other parts?
        g.add_node(R1.curie)
        g.add_edge(R2.curie, R1.curie, key=M1.curie, type=EXACT_MATCH.curie)
        g.add_edge(R1.curie, R2.curie, key=M1_INV.curie, type=EXACT_MATCH.curie)
        return g

    def initialize_autocomplete(self) -> None:
        """Mock initializing autocomplete."""

    def get_autocompletion(self, prefix: str, *, top_n: int = 100) -> AutocompletionResults:
        """Mock getting an autocompletion."""
        raise NotImplementedError(f"need mock for {prefix}")

    def get_example_concept(self) -> NormalizedNamableReference:
        """Mock getting an example concept."""
        return R2


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
            res = client.get(f"/mapping_set/?id={TEST_MAPPING_SET.id}")
            self.assertEqual(200, res.status_code, msg=res.text)

    def test_concept(self) -> None:
        """Test the mapping set page."""
        with self.flask_app.test_client() as client:
            res = client.get(f"/concept/{R2.curie}")
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
        self.assertEqual(M1.evidence[0], SimpleEvidence.model_validate(res.json()))

        res_not_found = self.test_client.get(f"/api/evidence/{E1_M2_REFERENCE.curie}")
        self.assertEqual(404, res_not_found.status_code, msg=f"got result: {res_not_found.text}")

    def test_mapping_set(self) -> None:
        """Test the mapping set API."""
        res = self.test_client.get(f"/api/mapping_set/?id={TEST_MAPPING_SET.id}")
        self.assertEqual(200, res.status_code)
        self.assertEqual(TEST_MAPPING_SET, MappingSet.model_validate(res.json()))

        # malformed
        res_not_found = self.test_client.get("/api/mapping_set/?id=abcdef")
        self.assertEqual(422, res_not_found.status_code)

        res_not_found = self.test_client.get("/api/mapping_set/?id=https://example.com/test.tsv")
        self.assertEqual(404, res_not_found.status_code)

        res_all = self.test_client.get("/api/mapping_set/")
        self.assertEqual(200, res_all.status_code, msg=res_all.text)
        self.assertEqual([TEST_MAPPING_SET], [MappingSet.model_validate(r) for r in res_all.json()])

    def test_mapping(self) -> None:
        """Test the mapping API."""
        res = self.test_client.get(f"/api/mapping/{M1.curie}")
        self.assertEqual(200, res.status_code)
        self.assertEqual(M1, Mapping.model_validate(res.json()))

        res_not_found = self.test_client.get("/api/mapping/abcdef")
        self.assertEqual(404, res_not_found.status_code)

    def test_exact_matches(self) -> None:
        """Test the exact matches API."""
        res = self.test_client.get(f"/api/exact/{R2.curie}")
        self.assertEqual(200, res.status_code)
        records = res.json()
        self.assertEqual(
            [R1], [Reference.model_validate(r) for r in records], msg=f"Results: {records}"
        )

        res_not_found = self.test_client.get("/api/exact/abcdef")
        self.assertEqual(404, res_not_found.status_code)

    def test_component(self) -> None:
        """Test the connected components API."""
        res = self.test_client.get(f"/api/cytoscape/{R2.curie}")
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
