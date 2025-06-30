"""Reusable assets for testing."""

from __future__ import annotations

import unittest

from semra import Mapping, Reference
from semra.api import Index, get_index

a1_curie = "CHEBI:10084"  # Xylopinine
a2_curie = "CHEBI:10100"  # zafirlukast
b1_curie = "mesh:C453820"  # xylopinine
b2_curie = "mesh:C062735"  # zafirlukast
a1, a2 = (
    Reference.from_curie(a1_curie.lower(), name="Xylopinine"),
    Reference.from_curie(a2_curie.lower(), name="zafirlukast"),
)
b1, b2 = (
    Reference.from_curie(b1_curie, name="xylopinine"),
    Reference.from_curie(b2_curie, name="zafirlukast"),
)

TEST_CURIES = {a1, a2, b1, b2}


class BaseTestCase(unittest.TestCase):
    """A test case with functionality for testing mapping equivalence."""

    def assert_same_triples(
        self,
        expected_mappings: Index | list[Mapping],
        actual_mappings: Index | list[Mapping],
        msg: str | None = None,
    ) -> None:
        """Assert that two sets of mappings are the same."""
        if not isinstance(expected_mappings, dict):
            expected_mappings = get_index(expected_mappings, progress=False)
        if not isinstance(actual_mappings, dict):
            actual_mappings = get_index(actual_mappings, progress=False)

        self.assertEqual(
            self._clean_index(expected_mappings),
            self._clean_index(actual_mappings),
            msg=msg,
        )

    @staticmethod
    def _clean_index(index: Index) -> list[str]:
        triples = sorted(set(index))
        return [
            f"<{triple.subject.curie}, {triple.predicate.curie}, {triple.object.curie}>"
            for triple in triples
        ]
