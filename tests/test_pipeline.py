"""Tests for the automated assembly pipeline."""

import tempfile
import unittest
from collections.abc import Collection
from pathlib import Path
from typing import cast

from curies import Triple

import semra
from semra.api import get_index
from semra.io import write_sssom
from semra.pipeline import AssembleReturnType, Configuration, Input, MappingPack, get_raw_mappings
from semra.sources import SOURCE_RESOLVER
from semra.struct import Mapping, MappingSet, Reference, SimpleEvidence
from semra.vocabulary import CHARLIE, DB_XREF, EXACT_MATCH, MANUAL_MAPPING
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
                author=CHARLIE,
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
        self.assertEqual(CHARLIE.pair, cast(Reference, ev.author).pair)
        self.assertIsNotNone(ev.mapping_set)
        mapping_set: MappingSet = cast(MappingSet, ev.mapping_set)
        self.assertEqual("test", mapping_set.name)
        self.assertEqual(1.0, mapping_set.confidence)

    def test_custom(self) -> None:
        """Test using custom sources in the configuration."""
        inp = Input(source="custom", prefix="get_test_mappings")
        with tempfile.TemporaryDirectory() as directory:
            config = Configuration(
                inputs=[inp],
                priority=["chebi", "mesh"],
                key="test",
                name="Test Configuration",
                description="Tests using custom sources",
                directory=Path(directory),
            )
            mappings = get_raw_mappings(config, show_progress=False)
        self.assert_test_mappings(mappings)

    def test_sssom(self) -> None:
        """Test using SSSOM sources in the configuration."""
        with tempfile.TemporaryDirectory() as d:
            path = Path(d).resolve().joinpath("test.sssom.tsv")
            res = write_sssom(TEST_MAPPINGS, path)
            self.assertIsNone(res, msg="streaming should not be activated")

            inp = Input(source="sssom", prefix=path.as_posix(), extras={"mapping_set_name": "test"})
            config = Configuration(
                inputs=[inp],
                priority=["a", "b"],
                key="test",
                name="Test Configuration",
                description="Tests using SSSOM sources",
                directory=Path(d).joinpath("output"),
            )
            mappings = get_raw_mappings(config, show_progress=False)
            self.assert_test_mappings(mappings)

    def test_sssom_stream(self) -> None:
        """Test writing SSSOM with a stream."""
        with tempfile.TemporaryDirectory() as d:
            path = Path(d).resolve().joinpath("test.sssom.tsv")
            write_sssom(TEST_MAPPINGS, path, prune=False, add_labels=False)

    def test_taxrank(self) -> None:
        """A configuration for assembling mappings for taxonomical rank terms."""
        priority = [
            "taxrank",
            "ncbitaxon",
            "tdwg.taxonrank",
        ]
        with tempfile.TemporaryDirectory() as directory:
            configuration = semra.Configuration(
                key="taxrank",
                name="Taxonomical Ranks",
                inputs=[
                    semra.Input(prefix="taxrank", source="pyobo", confidence=0.99),
                ],
                negative_inputs=[],
                priority=priority,
                mutations=[
                    # This means, take all mappings where either the subject or object is taxrank,
                    # and the predicicate is dbxref and upgrade it to be exact match
                    semra.Mutation(source="taxrank", confidence=0.99, old=DB_XREF, new=EXACT_MATCH),
                ],
                directory=Path(directory),
                remove_imprecise=True,
            )
            m: MappingPack = configuration.get_mappings(
                return_type=AssembleReturnType.all,
                refresh_processed=True,
            )

        self.assertNotEqual([], m.raw, msg="empty raw mappings")
        msg_part = "\n".join(" - ".join(m.as_str_triple()) for m in m.raw)
        self.assertNotEqual(
            [],
            m.processed,
            msg=f"empty processed mappings. had {len(m.raw):,} raw mappings:\n\n{msg_part}",
        )
        self.assertNotEqual([], m.priority, msg="empty priority mappings")

        index = get_index(m.processed, progress=False)

        self.assert_triple_not_in(
            Triple(
                subject=Reference.from_curie("taxrank:0000001"),
                predicate=DB_XREF,
                object=Reference.from_curie("ncbitaxon:phylum"),
            ),
            index,
            msg="should not have oboInOwl database cross-reference relations",
        )

        self.assert_triple_in(
            Triple(
                subject=Reference.from_curie("taxrank:0000001"),
                predicate=EXACT_MATCH,
                object=Reference.from_curie("ncbitaxon:phylum"),
            ),
            index,
        )

    def assert_triple_in(
        self, triple: Triple, triples: Collection[Triple], msg: str | None = None
    ) -> None:
        """Assert triples."""
        triple_strs = {t.as_str_triple() for t in triples}
        self.assertNotEqual(0, len(triple_strs), msg="get empty mapping index")
        self.assertIn(triple.as_str_triple(), triple_strs, msg=msg)

    def assert_triple_not_in(
        self, triple: Triple, triples: Collection[Triple], msg: str | None = None
    ) -> None:
        """Assert triples."""
        triple_strs = {t.as_str_triple() for t in triples}
        self.assertNotEqual(0, len(triple_strs), msg="get empty mapping index")
        self.assertNotIn(triple.as_str_triple(), triple_strs, msg=msg)
