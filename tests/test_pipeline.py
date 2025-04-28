"""Tests for the automated assembly pipeline."""

import tempfile
import unittest
from pathlib import Path
from typing import cast

from curies import Reference

from semra import EXACT_MATCH, Mapping, MappingSet, SimpleEvidence
from semra.io import write_sssom
from semra.pipeline import Configuration, Input, get_raw_mappings
from semra.rules import MANUAL_MAPPING, charlie
from semra.sources import SOURCE_RESOLVER
from tests.constants import a1, b1

TEST_MAPPING_SET = MappingSet(
    name="test",
    confidence=1.0,
)
TEST_MAPPINGS = [
    Mapping(
        subject=a1,
        predicate=EXACT_MATCH,
        object=b1,
        evidence=[
            SimpleEvidence(
                justification=MANUAL_MAPPING,
                mapping_set=TEST_MAPPING_SET,
                author=charlie,
            )
        ],
    )
]


def get_test_mappings() -> list[Mapping]:
    """Get test mappings."""
    return TEST_MAPPINGS


# Register a function for getting test mappings in order to test the way Inputs are handled
SOURCE_RESOLVER.register(get_test_mappings)


class TestPipeline(unittest.TestCase):
    """Test case for the automated assembly pipeline."""

    def assert_test_mappings(self, mappings: list[Mapping]) -> None:
        """Check that the mappings are the test mappings."""
        self.assertEqual(1, len(mappings))
        mapping = mappings[0]
        self.assertIsInstance(mapping, Mapping)
        self.assertEqual(a1, mapping.subject)
        self.assertEqual(b1, mapping.object)
        self.assertEqual(1, len(mapping.evidence))
        ev = mapping.evidence[0]
        self.assertIsInstance(ev, SimpleEvidence)
        self.assertEqual(MANUAL_MAPPING, ev.justification)
        self.assertIsNotNone(ev.author)
        self.assertEqual(charlie.pair, cast(Reference, ev.author).pair)
        self.assertIsNotNone(ev.mapping_set)
        mapping_set: MappingSet = cast(MappingSet, ev.mapping_set)
        self.assertEqual("test", mapping_set.name)
        self.assertEqual(1.0, mapping_set.confidence)

    def test_custom(self) -> None:
        """Test using custom sources in the configuration."""
        inp = Input(source="custom", prefix="get_test_mappings")
        config = Configuration(
            inputs=[inp],
            priority=["chebi", "mesh"],
            key="test",
            name="Test Configuration",
            description="Tests using custom sources",
        )
        mappings = get_raw_mappings(config, show_progress=False)
        self.assert_test_mappings(mappings)

    def test_sssom(self) -> None:
        """Test using SSSOM sources in the configuration."""
        with tempfile.TemporaryDirectory() as d:
            path = Path(d).resolve().joinpath("test.sssom.tsv")
            write_sssom(TEST_MAPPINGS, path)

            inp = Input(source="sssom", prefix=path.as_posix(), extras={"mapping_set_name": "test"})
            config = Configuration(
                inputs=[inp],
                priority=["a", "b"],
                key="test",
                name="Test Configuration",
                description="Tests using SSSOM sources",
            )
            mappings = get_raw_mappings(config, show_progress=False)
            self.assert_test_mappings(mappings)

    def test_sssom_stream(self) -> None:
        """Test writing SSSOM with a stream."""
        with tempfile.TemporaryDirectory() as d:
            path = Path(d).resolve().joinpath("test.sssom.tsv")
            write_sssom(TEST_MAPPINGS, path, prune=False, add_labels=False)
