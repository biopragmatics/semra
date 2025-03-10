"""Tests for the automated assembly pipeline."""

import tempfile
import unittest
from pathlib import Path

from curies.vocabulary import charlie

from semra import EXACT_MATCH, Mapping, MappingSet, SimpleEvidence
from semra.io import write_sssom
from semra.pipeline import Configuration, Input, get_raw_mappings
from semra.rules import MANUAL_MAPPING
from semra.sources import SOURCE_RESOLVER
from tests.constants import a1, b1

TEST_MAPPING_SET = MappingSet(
    name="test",
    confidence=1.0,
)
TEST_MAPPINGS = [
    Mapping(
        s=a1,
        p=EXACT_MATCH,
        o=b1,
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

    def assert_test_mappings(self, mappings):
        """Check that the mappings are the test mappings."""
        self.assertEqual(1, len(mappings))
        mapping = mappings[0]
        self.assertIsInstance(mapping, Mapping)
        self.assertEqual(a1, mapping.s)
        self.assertEqual(b1, mapping.o)
        self.assertEqual(1, len(mapping.evidence))
        ev = mapping.evidence[0]
        self.assertIsInstance(ev, SimpleEvidence)
        self.assertEqual(MANUAL_MAPPING, ev.justification)
        self.assertEqual(charlie.pair, ev.author.pair)
        self.assertIsNotNone(ev.mapping_set)
        self.assertEqual("test", ev.mapping_set.name)
        self.assertEqual(1.0, ev.mapping_set.confidence)

    def test_custom(self):
        """Test using custom sources in the configuration."""
        inp = Input(source="custom", prefix="get_test_mappings")
        config = Configuration(
            inputs=[inp],
            priority=["chebi", "mesh"],
            name="Test Configuration",
            description="Tests using custom sources",
        )
        mappings = get_raw_mappings(config, show_progress=False)
        self.assert_test_mappings(mappings)

    def test_sssom(self):
        """Test using SSSOM sources in the configuration."""
        with tempfile.TemporaryDirectory() as d:
            path = Path(d).resolve().joinpath("test.sssom.tsv")
            write_sssom(TEST_MAPPINGS, path)

            inp = Input(source="sssom", prefix=path.as_posix(), extras={"mapping_set_name": "test"})
            config = Configuration(
                inputs=[inp],
                priority=["a", "b"],
                name="Test Configuration",
                description="Tests using SSSOM sources",
            )
            mappings = get_raw_mappings(config, show_progress=False)
            self.assert_test_mappings(mappings)
