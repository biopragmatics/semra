"""Test the app."""

import unittest
from typing import ClassVar

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
    SimpleEvidence,
)
from semra.client import BaseClient, FullSummary, ReferenceHint
from semra.wsgi import get_app
from tests.constants import a1, a2, b1, b2

MS1 = MappingSet(
    name="Test Mapping Set",
)
E1 = SimpleEvidence(
    mapping_set=MS1,
    justification=UNSPECIFIED_MAPPING,
)
M1 = Mapping(subject=a1, predicate=EXACT_MATCH, object=b1, evidence=[E1])
M2 = Mapping(subject=a2, predicate=EXACT_MATCH, object=b2, evidence=[E1])
TEST_MAPPINGS = [M1, M2]
E1_M1_REFERENCE = E1.get_reference(M1)
E1_M2_REFERENCE = E1.get_reference(M2)


class MockClient(BaseClient):
    """A mock client."""

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

    def get_full_summary(self) -> FullSummary:
        """Get an empty summary."""
        return FullSummary()


class TestAPI(unittest.TestCase):
    """Test the app."""

    dao: ClassVar[BaseClient]
    flask_app: ClassVar[Flask]
    fastapi_app: ClassVar[FastAPI]
    test_client: ClassVar[TestClient]

    @classmethod
    def setUpClass(cls) -> None:
        """Set up the class with a mock client and app."""
        cls.dao = MockClient()
        cls.flask_app, cls.fastapi_app = get_app(
            client=cls.dao, return_flask=True, use_biomappings=False
        )
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
