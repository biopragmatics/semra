"""Test the app."""

import unittest

from starlette.testclient import TestClient

from semra import (
    EXACT_MATCH,
    UNSPECIFIED_MAPPING,
    Evidence,
    Mapping,
    MappingSet,
    Reference,
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

    def get_full_summary(self) -> FullSummary:
        """Get an empty summary."""
        return FullSummary()


class TestApp(unittest.TestCase):
    """Test the app."""

    def test_app(self) -> None:
        """Test the app."""
        client = MockClient()
        _flask_app, fastapi_app = get_app(client=client, return_flask=True)

        test_client = TestClient(fastapi_app)

        # Test evidence API
        res1 = test_client.get(f"/api/evidence/{E1_M1_REFERENCE.curie}")
        self.assertEqual(200, res1.status_code)
        self.assertEqual(E1, SimpleEvidence.model_validate(res1.json()))

        res2 = test_client.get(f"/api/evidence/{E1_M2_REFERENCE.curie}")
        self.assertEqual(404, res2.status_code)

        # Test mapping set API
        res3 = test_client.get(f"/api/mapping_set/{MS1.curie}")
        self.assertEqual(200, res1.status_code)
        self.assertEqual(MS1, MappingSet.model_validate(res3.json()))

        res4 = test_client.get("/api/mapping_set/abcdef")
        self.assertEqual(404, res4.status_code)

        res5 = test_client.get("/api/mapping_set/")
        self.assertEqual(200, res1.status_code)
        self.assertEqual([MS1], [MappingSet.model_validate(r) for r in res5.json()])

        # Test mapping API
        res6 = test_client.get(f"/api/mapping/{M1.curie}")
        self.assertEqual(200, res1.status_code)
        self.assertEqual(M1, Mapping.model_validate(res6.json()))

        res7 = test_client.get("/api/mapping/abcdef")
        self.assertEqual(404, res7.status_code)

        # Test concept API
        res8 = test_client.get(f"/api/concept/{a1.curie}")
        self.assertEqual(200, res1.status_code)
        self.assertEqual(a1, Reference.model_validate(res8.json()))

        res9 = test_client.get("/api/concept/abcasdef")
        self.assertEqual(404, res9.status_code)
