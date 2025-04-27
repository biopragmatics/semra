"""Tests for I/O functions."""

import getpass
import unittest
import uuid

import pandas as pd

from semra import Mapping, MappingSet, SimpleEvidence
from semra.io import from_pyobo, from_sssom_df
from semra.rules import EXACT_MATCH, UNSPECIFIED_MAPPING
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


class TestIO(unittest.TestCase):
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
