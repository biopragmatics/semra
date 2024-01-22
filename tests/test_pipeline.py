"""Tests for the automated assembly pipeline."""

import tempfile
import typing as t
import unittest
from pathlib import Path

from semra import EXACT_MATCH, Mapping, MappingSet, Reference, SimpleEvidence
from semra.io import write_sssom
from semra.pipeline import Configuration, Input, get_raw_mappings
from semra.rules import CHARLIE_ORCID, MANUAL_MAPPING
from semra.sources import SOURCE_RESOLVER

TEST_MAPPING_SET = MappingSet(
    name="test",
    confidence=1.0,
)
TEST_MAPPINGS = [
    Mapping(
        s=Reference.from_curie("a:1"),
        p=EXACT_MATCH,
        o=Reference.from_curie("b:1"),
        evidence=[
            SimpleEvidence(
                justification=MANUAL_MAPPING,
                mapping_set=TEST_MAPPING_SET,
                author=CHARLIE_ORCID,
            )
        ],
    )
]


def get_test_mappings() -> t.List[Mapping]:
    """A test function to get mappings."""
    return TEST_MAPPINGS


SOURCE_RESOLVER.register(get_test_mappings)


class TestPipeline(unittest.TestCase):
    """Test case for the automated assembly pipeline."""

    def assert_test_mappings(self, mappings):
        """Check that the mappings are the test mappings."""
        self.assertEqual(1, len(mappings))
        mapping = mappings[0]
        self.assertIsInstance(mapping, Mapping)
        self.assertEqual("a", mapping.s.prefix)
        self.assertEqual("b", mapping.o.prefix)
        self.assertEqual(1, len(mapping.evidence))
        ev = mapping.evidence[0]
        self.assertIsInstance(ev, SimpleEvidence)
        self.assertEqual(MANUAL_MAPPING, ev.justification)
        self.assertEqual(CHARLIE_ORCID, ev.author)
        self.assertIsNotNone(ev.mapping_set)
        self.assertEqual("test", ev.mapping_set.name)
        self.assertEqual(1.0, ev.mapping_set.confidence)

    def test_custom(self):
        """Test using custom sources in the configuration."""
        inp = Input(source="custom", prefix="get_test_mappings")
        config = Configuration(
            inputs=[inp], priority=["a", "b"], name="Test Configuration", description="Tests using custom sources"
        )
        mappings = get_raw_mappings(config)
        self.assert_test_mappings(mappings)

    def test_sssom(self):
        """Test using SSSOM sources in the configuration."""
        with tempfile.TemporaryDirectory() as d:
            path = Path(d).resolve().joinpath("test.sssom.tsv")
            write_sssom(TEST_MAPPINGS, path)

            inp = Input(source="sssom", prefix=path.as_posix(), extras={"mapping_set_name": "test"})
            config = Configuration(
                inputs=[inp], priority=["a", "b"], name="Test Configuration", description="Tests using SSSOM sources"
            )
            mappings = get_raw_mappings(config)
            self.assert_test_mappings(mappings)
