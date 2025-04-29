"""Tests for I/O functions."""

import getpass
import tempfile
import unittest
import uuid
from pathlib import Path

import pandas as pd

from semra import Mapping, MappingSet, ReasonedEvidence, Reference, SimpleEvidence
from semra.io import (
    from_digraph,
    from_jsonl,
    from_multidigraph,
    from_pyobo,
    from_sssom_df,
    from_sssom,
    write_sssom,
    to_digraph,
    to_multidigraph,
    from_pickle, write_pickle,
    write_jsonl,
)
from semra.rules import (
    BEN_ORCID,
    CHAIN_MAPPING,
    EXACT_MATCH,
    LEXICAL_MAPPING,
    MANUAL_MAPPING,
    UNSPECIFIED_MAPPING,
    charlie,
)
from tests.constants import a1, a1_curie, a2, a2_curie, b1, b1_curie, b2, b2_curie

LOCAL = getpass.getuser() == "cthoyt"
CONST_UUID = uuid.uuid4()

mapping_set_name = "test"
mapping_set_confidence = 0.6


@unittest.skipUnless(LOCAL, reason="Don't test remotely since PyOBO content isn't available")
class TestIOLocal(unittest.TestCase):
    """Test I/O functions that only run if pyobo is available."""

    def test_from_pyobo(self) -> None:
        """Test loading content from PyOBO."""
        mappings = from_pyobo("doid")
        for mapping in mappings:
            self.assertEqual("doid", mapping.s.prefix)

        mappings_2 = from_pyobo("doid", "mesh")
        for mapping in mappings_2:
            self.assertEqual("doid", mapping.s.prefix)
            self.assertEqual("mesh", mapping.o.prefix)


class TestSSSOM(unittest.TestCase):
    """Tests for I/O functions."""

    def test_from_sssom_df(self) -> None:
        """Test importing mappings from a SSSOM dataframe."""
        expected_evidence = SimpleEvidence(
            mapping_set=MappingSet(
                name=mapping_set_name,
                confidence=mapping_set_confidence,
            ),
            justification=UNSPECIFIED_MAPPING,
            uuid=CONST_UUID,
        )
        expected_mappings = [
            Mapping(s=a1, p=EXACT_MATCH, o=b1, evidence=[expected_evidence]),
            Mapping(s=a2, p=EXACT_MATCH, o=b2, evidence=[expected_evidence]),
        ]

        # Test 1 - from kwargs
        rows = [
            (a1_curie, "skos:exactMatch", "exact match", b1_curie),
            (a2_curie, "skos:exactMatch", "exact match", b2_curie),
        ]
        columns = [
            "subject_id",
            "predicate_id",
            "predicate_label",
            "object_id",
        ]
        df = pd.DataFrame(rows, columns=columns)
        actual_mappings = from_sssom_df(
            df,
            mapping_set_name=mapping_set_name,
            mapping_set_confidence=mapping_set_confidence,
            _uuid=CONST_UUID,
        )
        self.assertEqual(expected_mappings, actual_mappings)

        # Test 2 - from columns (partial)
        rows_test_2 = [
            (a1_curie, "skos:exactMatch", "exact match", b1_curie, mapping_set_name),
            (a2_curie, "skos:exactMatch", "exact match", b2_curie, mapping_set_name),
        ]
        columns = [
            "subject_id",
            "predicate_id",
            "predicate_label",
            "object_id",
            "mapping_set_name",
        ]
        df = pd.DataFrame(rows_test_2, columns=columns)
        actual_mappings = from_sssom_df(
            df,
            mapping_set_confidence=mapping_set_confidence,
            _uuid=CONST_UUID,
        )
        self.assertEqual(expected_mappings, actual_mappings)

        # Test 3 - from columns (full)
        rows_test_3 = [
            (
                a1_curie,
                "skos:exactMatch",
                "exact match",
                b1_curie,
                mapping_set_name,
                mapping_set_confidence,
            ),
            (
                a2_curie,
                "skos:exactMatch",
                "exact match",
                b2_curie,
                mapping_set_name,
                mapping_set_confidence,
            ),
        ]
        columns = [
            "subject_id",
            "predicate_id",
            "predicate_label",
            "object_id",
            "mapping_set_name",
            "mapping_set_confidence",
        ]
        df = pd.DataFrame(rows_test_3, columns=columns)
        actual_mappings = from_sssom_df(df, _uuid=CONST_UUID)
        self.assertEqual(expected_mappings, actual_mappings)

    def test_from_sssom_df_with_license(self) -> None:
        """Test loading a SSSOM dataframe that has a license."""
        test_license = "CC0"
        test_version = "1.0"
        expected_evidence = SimpleEvidence(
            mapping_set=MappingSet(
                name=mapping_set_name,
                confidence=mapping_set_confidence,
                license=test_license,
                version=test_version,
            ),
            justification=UNSPECIFIED_MAPPING,
            uuid=CONST_UUID,
        )
        expected_mappings = [
            Mapping(s=a1, p=EXACT_MATCH, o=b1, evidence=[expected_evidence]),
            Mapping(s=a2, p=EXACT_MATCH, o=b2, evidence=[expected_evidence]),
        ]

        rows = [
            (a1_curie, "skos:exactMatch", "exact match", b1_curie),
            (a2_curie, "skos:exactMatch", "exact match", b2_curie),
        ]
        columns = [
            "subject_id",
            "predicate_id",
            "predicate_label",
            "object_id",
        ]
        df = pd.DataFrame(rows, columns=columns)
        actual_mappings = from_sssom_df(
            df,
            _uuid=CONST_UUID,
            mapping_set_name=mapping_set_name,
            mapping_set_confidence=mapping_set_confidence,
            license=test_license,
            version=test_version,
        )
        self.assertEqual(expected_mappings, actual_mappings)


class TestIO(unittest.TestCase):
    """Test I/O funcitons."""

    def setUp(self) -> None:
        """Set up the test case."""
        r1 = Reference.from_curie("mesh:C406527", name="R 115866")
        r2 = Reference.from_curie("chebi:101854", name="talarozole")
        r3 = Reference.from_curie("chembl.compound:CHEMBL459505", name="TALAROZOLE")

        t1 = r1, EXACT_MATCH, r2
        t2 = r2, EXACT_MATCH, r3
        t3 = r1, EXACT_MATCH, r3

        biomappings = MappingSet(name="biomappings", confidence=0.90, license="CC0")
        chembl = MappingSet(name="chembl", confidence=0.90, license="CC-BY-SA-3.0")
        lexical_ms = MappingSet(name="lexical", confidence=0.90)

        m1_e1 = SimpleEvidence(
            mapping_set=biomappings, justification=MANUAL_MAPPING, author=charlie, confidence=0.99
        )

        # check that making an identical evidence gives the same hex digest
        m1_e1_copy = SimpleEvidence(
            mapping_set=biomappings, justification=MANUAL_MAPPING, author=charlie, confidence=0.99
        )
        self.assertEqual(m1_e1.hexdigest(t1), m1_e1_copy.hexdigest(t1))

        m1_e2 = SimpleEvidence(
            mapping_set=biomappings, justification=MANUAL_MAPPING, author=BEN_ORCID, confidence=0.94
        )
        m1_e3 = SimpleEvidence(
            mapping_set=lexical_ms, justification=LEXICAL_MAPPING, confidence=0.8
        )

        m1 = Mapping.from_triple(t1, evidence=[m1_e1, m1_e2, m1_e3])

        m2_e1 = SimpleEvidence(
            mapping_set=chembl, justification=UNSPECIFIED_MAPPING, confidence=0.90
        )
        m2 = Mapping.from_triple(t2, evidence=[m2_e1])

        m3_e1 = ReasonedEvidence(justification=CHAIN_MAPPING, mappings=[m1, m2])
        m3 = Mapping.from_triple(t3, evidence=[m3_e1])

        self.mappings = [m1, m2, m3]

    def test_jsonl(self) -> None:
        """Test JSONL I/O."""
        with tempfile.TemporaryDirectory() as directory_:
            for path in [
                Path(directory_).joinpath("test.jsonl"),
                Path(directory_).joinpath("test.jsonl.gz"),
            ]:
                write_jsonl(self.mappings, path)
                new_mappings = from_jsonl(path, show_progress=False)
                self.assertEqual(self.mappings, new_mappings)

    def test_digraph(self) -> None:
        """Test I/O to a directed graph."""
        self.assertEqual(sorted(self.mappings), sorted(from_digraph(to_digraph(self.mappings))))

    def test_multidigraph(self) -> None:
        """Test I/O with multi-directed graph."""
        self.assertEqual(
            sorted(self.mappings), sorted(from_multidigraph(to_multidigraph(self.mappings)))
        )

    def test_pickle(self) -> None:
        """Test I/O with pickle."""
        with tempfile.TemporaryDirectory() as directory_:
            for path in [
                Path(directory_).joinpath("test.pkl"),
                Path(directory_).joinpath("test.pkl.gz"),
            ]:
                write_pickle(self.mappings, path)
                new_mappings = from_pickle(path)
                self.assertEqual(self.mappings, new_mappings)

    def test_sssom(self) -> None:
        """Test I/O with SSSOM."""
        with tempfile.TemporaryDirectory() as directory_:
            for path in [
                Path(directory_).joinpath("test.sssom.tsv"),
                Path(directory_).joinpath("test.sssom.tsv.gz"),
            ]:
                write_sssom(self.mappings, path)
                new_mappings = from_sssom(path)
                self.assertEqual(sorted(self.mappings), sorted(new_mappings))
