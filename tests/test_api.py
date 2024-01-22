from __future__ import annotations

import typing as t
import unittest

from semra import api
from semra.api import (
    BROAD_MATCH,
    DB_XREF,
    EXACT_MATCH,
    NARROW_MATCH,
    Index,
    filter_mappings,
    filter_self_matches,
    flip,
    get_index,
    get_many_to_many,
    infer_chains,
    infer_mutations,
    infer_reversible,
    keep_prefixes,
    project,
)
from semra.rules import KNOWLEDGE_MAPPING, MANUAL_MAPPING
from semra.struct import Mapping, MappingSet, ReasonedEvidence, Reference, SimpleEvidence, line, triple_key


def _get_references(n: int, prefix: str = "test") -> t.List[Reference]:
    return [Reference(prefix=prefix, identifier=str(i)) for i in range(1, n + 1)]


def _exact(s, o, evidence: t.Optional[t.List[SimpleEvidence]] = None) -> Mapping:
    return Mapping(s=s, p=EXACT_MATCH, o=o, evidence=evidence or [])


EV = SimpleEvidence(
    justification=MANUAL_MAPPING,
    mapping_set=MappingSet(name="test_mapping_set", confidence=0.95),
)
MS = MappingSet(name="test", confidence=0.95)


class TestOperations(unittest.TestCase):
    def test_path(self):
        """Test quickly creating mapping lists."""
        r1, r2, r3 = _get_references(3)
        m1 = Mapping(s=r1, p=EXACT_MATCH, o=r2)
        m2 = Mapping(s=r2, p=BROAD_MATCH, o=r3)
        self.assertEqual([m1], line(r1, EXACT_MATCH, r2))
        self.assertEqual([m1, m2], line(r1, EXACT_MATCH, r2, BROAD_MATCH, r3))

    def test_flip_symmetric(self):
        """Test flipping a symmetric relation (e.g., exact match)."""
        chebi_reference = Reference(prefix="chebi", identifier="10001")
        mesh_reference = Reference(prefix="mesh", identifier="C067604")
        mapping = Mapping(s=chebi_reference, p=EXACT_MATCH, o=mesh_reference, evidence=[EV])
        new_mapping = flip(mapping)
        self.assertIsNotNone(new_mapping)
        self.assertEqual(mesh_reference, new_mapping.s)
        self.assertEqual(EXACT_MATCH, new_mapping.p)
        self.assertEqual(chebi_reference, new_mapping.o)
        self.assertEqual(1, len(new_mapping.evidence))
        self.assertIsInstance(new_mapping.evidence[0], ReasonedEvidence)
        self.assertIsInstance(new_mapping.evidence[0].mappings[0].evidence[0], SimpleEvidence)
        self.assertEqual(EV, new_mapping.evidence[0].mappings[0].evidence[0])

    def test_flip_asymmetric(self):
        """Test flipping asymmetric relations (e.g., narrow and broad match)."""
        docetaxel_mesh = Reference(prefix="mesh", identifier="D000077143")
        docetaxel_anhydrous_chebi = Reference(prefix="chebi", identifier="4672")
        narrow_mapping = Mapping(s=docetaxel_mesh, p=NARROW_MATCH, o=docetaxel_anhydrous_chebi)
        broad_mapping = Mapping(o=docetaxel_mesh, p=BROAD_MATCH, s=docetaxel_anhydrous_chebi)

        actual = flip(narrow_mapping)
        self.assertIsNotNone(actual)
        self.assertEqual(docetaxel_anhydrous_chebi, actual.s)
        self.assertEqual(BROAD_MATCH, actual.p)
        self.assertEqual(docetaxel_mesh, actual.o)

        actual = flip(broad_mapping)
        self.assertIsNotNone(actual)
        self.assertEqual(docetaxel_mesh, actual.s)
        self.assertEqual(NARROW_MATCH, actual.p)
        self.assertEqual(docetaxel_anhydrous_chebi, actual.o)

    def test_index(self):
        r1, r2 = _get_references(2)
        e1 = SimpleEvidence(justification=Reference(prefix="semapv", identifier="LexicalMatching"), mapping_set=MS)
        e2 = SimpleEvidence(
            justification=Reference(prefix="semapv", identifier="ManualMappingCuration"), mapping_set=MS
        )
        m1 = Mapping(s=r1, p=EXACT_MATCH, o=r2, evidence=[e1])
        m2 = Mapping(s=r1, p=EXACT_MATCH, o=r2, evidence=[e2])
        index = get_index([m1, m2], progress=False)
        self.assertIn(m1.triple, index)
        self.assertEqual(1, len(index))
        self.assertEqual(2, len(index[m1.triple]))
        self.assertEqual(
            {"LexicalMatching", "ManualMappingCuration"},
            {e.justification.identifier for e in index[m1.triple]},
        )

    def assert_same_triples(
        self,
        expected_mappings: t.Union[Index, t.List[Mapping]],
        actual_mappings: t.Union[Index, t.List[Mapping]],
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
    def _clean_index(index: Index) -> t.List[str]:
        triples = sorted(set(index), key=triple_key)
        return ["<" + ", ".join(element.curie for element in triple) + ">" for triple in triples]

    def test_infer_exact_match(self):
        """Test inference through the transitivity of SKOS exact matches."""
        r1, r2, r3, r4 = _get_references(4)
        m1, m2, m3 = line(r1, EXACT_MATCH, r2, EXACT_MATCH, r3, EXACT_MATCH, r4)
        m4 = _exact(r1, r3)
        m5 = _exact(r1, r4)
        m6 = _exact(r2, r4)
        m4_inv, m5_inv, m6_inv = (flip(m) for m in (m4, m5, m6))

        backwards_msg = "backwards inference is not supposed to be done here"

        index = get_index(infer_chains([m1, m2], backwards=False, progress=False), progress=False)
        self.assertNotIn(m4_inv.triple, index, msg=backwards_msg)

        index = get_index(infer_chains([m1, m2, m3], backwards=False, progress=False), progress=False)
        self.assert_same_triples([m1, m2, m3, m4, m4, m5, m6], index)
        self.assertNotIn(m4_inv.triple, index, msg=backwards_msg)
        self.assertNotIn(m5_inv.triple, index, msg=backwards_msg)
        self.assertNotIn(m6_inv.triple, index, msg=backwards_msg)

        # m4's evidence should comprise a single complex evidence
        self.assertEqual(1, len(index[m4.triple]))
        m4_evidence = index[m4.triple][0]
        self.assertIsInstance(m4_evidence, ReasonedEvidence)
        self.assertEqual(2, len(m4_evidence.mappings))
        self.assertEqual([m1, m2], m4_evidence.mappings)

    def test_no_infer(self):
        """Test no inference happens over mixed chains of broad/narrow."""
        r1, r2, r3 = _get_references(3)

        m1, m2 = line(r1, NARROW_MATCH, r2, BROAD_MATCH, r3)
        self.assert_same_triples(
            [m1, m2], infer_chains([m1, m2], progress=False), msg="No inference between broad and narrow"
        )

        # ------ Same but in reverse ---------
        m1, m2 = line(r1, BROAD_MATCH, r2, NARROW_MATCH, r3)
        self.assert_same_triples(
            [m1, m2], infer_chains([m1, m2], progress=False), msg="No inference between broad and narrow"
        )

    def test_infer_broad_match_1(self):
        r1, r2, r3, r4 = _get_references(4)
        m1, m2, m3 = line(r1, EXACT_MATCH, r2, BROAD_MATCH, r3, EXACT_MATCH, r4)
        m4 = Mapping(s=r1, p=BROAD_MATCH, o=r3, evidence=[EV])
        m5 = Mapping(s=r1, p=BROAD_MATCH, o=r4, evidence=[EV])
        m6 = Mapping(s=r2, p=BROAD_MATCH, o=r4, evidence=[EV])
        m4_i = Mapping(o=r1, p=NARROW_MATCH, s=r3, evidence=[EV])
        m5_i = Mapping(o=r1, p=NARROW_MATCH, s=r4, evidence=[EV])
        m6_i = Mapping(o=r2, p=NARROW_MATCH, s=r4, evidence=[EV])

        # Check inference over two steps
        self.assert_same_triples(
            [m1, m2, m4],
            infer_chains([m1, m2], backwards=False, progress=False),
            msg="inference over two steps is broken",
        )
        self.assert_same_triples(
            [m1, m2, m4, m4_i],
            infer_chains([m1, m2], backwards=True, progress=False),
            msg="inference over two steps is broken",
        )

        self.assert_same_triples(
            [m1, m2, m3, m4, m5, m6],
            infer_chains([m1, m2, m3], backwards=False, progress=False),
            msg="inference over multiple steps is broken",
        )
        self.assert_same_triples(
            [m1, m2, m3, m4, m5, m6, m4_i, m5_i, m6_i],
            infer_chains([m1, m2, m3], backwards=True, progress=False),
            msg="inference over multiple steps is broken",
        )

    def test_infer_broad_match_2(self):
        r1, r2, r3, r4 = _get_references(4)
        m1, m2, m3 = line(r1, BROAD_MATCH, r2, EXACT_MATCH, r3, BROAD_MATCH, r4)
        m4 = Mapping(s=r1, p=BROAD_MATCH, o=r3)
        m5 = Mapping(s=r1, p=BROAD_MATCH, o=r4)
        m6 = Mapping(s=r2, p=BROAD_MATCH, o=r4)
        m4_i = Mapping(o=r1, p=NARROW_MATCH, s=r3)
        m5_i = Mapping(o=r1, p=NARROW_MATCH, s=r4)
        m6_i = Mapping(o=r2, p=NARROW_MATCH, s=r4)

        # Check inference over two steps
        self.assert_same_triples([m1, m2, m4], infer_chains([m1, m2], backwards=False, progress=False))
        self.assert_same_triples([m1, m2, m4, m4_i], infer_chains([m1, m2], backwards=True, progress=False))

        # Check inference over multiple steps
        self.assert_same_triples([m1, m2, m3, m4, m5, m6], infer_chains([m1, m2, m3], backwards=False, progress=False))
        self.assert_same_triples(
            [m1, m2, m3, m4, m5, m6, m4_i, m5_i, m6_i], infer_chains([m1, m2, m3], backwards=True, progress=False)
        )

    def test_infer_narrow_match(self):
        r1, r2, r3 = _get_references(3)
        m1, m2 = line(r1, EXACT_MATCH, r2, NARROW_MATCH, r3)
        m3 = Mapping(s=r1, p=NARROW_MATCH, o=r3)
        m3_i = Mapping(o=r1, p=BROAD_MATCH, s=r3)
        self.assert_same_triples([m1, m2, m3], infer_chains([m1, m2], backwards=False, progress=False))
        self.assert_same_triples([m1, m2, m3, m3_i], infer_chains([m1, m2], backwards=True, progress=False))

    def test_mixed_inference_1(self):
        r1, r2, r3 = _get_references(3)
        m1 = Mapping(s=r1, p=EXACT_MATCH, o=r2)
        m2 = Mapping(s=r2, p=NARROW_MATCH, o=r3)
        m3 = Mapping(s=r1, p=NARROW_MATCH, o=r3)

        m4 = Mapping(s=r2, p=EXACT_MATCH, o=r1)
        m5 = Mapping(s=r3, p=BROAD_MATCH, o=r2)
        m6 = Mapping(s=r3, p=BROAD_MATCH, o=r1)

        mappings = [m1, m2]
        mappings = infer_reversible(mappings, progress=False)
        self.assert_same_triples([m1, m2, m4, m5], mappings)

        mappings = infer_chains(mappings, progress=False)
        self.assert_same_triples([m1, m2, m3, m4, m5, m6], mappings)

    def test_filter_prefixes(self):
        """Test filtering out unwanted prefixes."""
        r11, r12 = _get_references(2, prefix="p1")
        r21, r22 = _get_references(2, prefix="p2")
        (r31,) = _get_references(1, prefix="p3")
        m1 = Mapping(s=r11, p=EXACT_MATCH, o=r21)
        m2 = Mapping(s=r12, p=EXACT_MATCH, o=r22)
        m3 = Mapping(s=r11, p=EXACT_MATCH, o=r31)
        mappings = [m1, m2, m3]
        self.assert_same_triples([m1, m2], keep_prefixes(mappings, {"p1", "p2"}, progress=False))

    def test_filter_self(self):
        """Test filtering out mappings within a given prefix."""
        r11, r12, r13 = _get_references(3, prefix="p1")
        r21, r22 = _get_references(2, prefix="p2")
        m1 = Mapping(s=r11, p=EXACT_MATCH, o=r21)
        m2 = Mapping(s=r12, p=EXACT_MATCH, o=r22)
        m3 = Mapping(s=r11, p=EXACT_MATCH, o=r13)
        mappings = [m1, m2, m3]
        self.assert_same_triples([m1, m2], filter_self_matches(mappings, progress=False))

    def test_filter_negative(self):
        """Test filtering out mappings within a given prefix."""
        r11, r12 = _get_references(2, prefix="p1")
        r21, r22 = _get_references(2, prefix="p2")
        m1 = Mapping(s=r11, p=EXACT_MATCH, o=r21)
        m2 = Mapping(s=r12, p=EXACT_MATCH, o=r22)
        mappings = [m1, m2]
        negative = [m2]
        self.assert_same_triples([m1], filter_mappings(mappings, negative, progress=False))

    def test_project(self):
        """Test projecting into a given source/target pair."""
        r11, r12 = _get_references(2, prefix="p1")
        r21, r22 = _get_references(2, prefix="p2")
        (r31,) = _get_references(1, prefix="p3")
        m1 = Mapping(s=r11, p=EXACT_MATCH, o=r21)
        m2 = Mapping(s=r12, p=EXACT_MATCH, o=r22)
        m2_i = Mapping(o=r12, p=EXACT_MATCH, s=r22)
        m3 = Mapping(s=r11, p=EXACT_MATCH, o=r31)
        mappings = [m1, m2, m2_i, m3]
        self.assert_same_triples([m1, m2], project(mappings, "p1", "p2", progress=False))

    def test_get_many_to_many(self):
        """Test getting many-to-many mappings."""
        a1, a2, a3 = _get_references(3, prefix="a")
        b1, b2, b3 = _get_references(3, prefix="b")

        # Subject duplicate
        m1 = Mapping(s=a1, p=EXACT_MATCH, o=b1)
        m2 = Mapping(s=a1, p=EXACT_MATCH, o=b3)
        m3 = Mapping(s=a2, p=EXACT_MATCH, o=b2)
        self.assert_same_triples([m1, m2], get_many_to_many([m1, m2, m3]))

        m4 = Mapping(s=a3, p=EXACT_MATCH, o=b2)
        self.assert_same_triples([m3, m4], get_many_to_many([m2, m3, m4]))

    def test_filter_confidence(self):
        """Test filtering by confidence."""
        (a1, a2) = _get_references(2, prefix="a")
        (b1, b2) = _get_references(2, prefix="b")
        m1 = Mapping(s=a1, p=DB_XREF, o=b1, evidence=[SimpleEvidence(confidence=0.95, mapping_set=MS)])
        m2 = Mapping(s=a1, p=DB_XREF, o=b1, evidence=[SimpleEvidence(confidence=0.65, mapping_set=MS)])
        mmm = list(api.filter_minimum_confidence([m1, m2], cutoff=0.7))
        self.assertEqual([m1], mmm)


class TestUpgrades(unittest.TestCase):
    """Test inferring mutations."""

    def test_infer_mutations(self):
        """Test inferring mutations."""
        (a1,) = _get_references(1, prefix="a")
        (b1,) = _get_references(1, prefix="b")
        original_confidence = 0.95
        mutation_confidence = 0.80
        m1 = Mapping(s=a1, p=DB_XREF, o=b1, evidence=[SimpleEvidence(confidence=original_confidence, mapping_set=MS)])
        new_mappings = infer_mutations(
            [m1], {("a", "b"): mutation_confidence}, old=DB_XREF, new=EXACT_MATCH, progress=False
        )
        self.assertEqual(2, len(new_mappings))
        new_m1, new_m2 = new_mappings
        self.assertEqual(m1, new_m1)
        self.assertEqual(a1, new_m2.s)
        self.assertEqual(EXACT_MATCH, new_m2.p)
        self.assertEqual(b1, new_m2.o)
        self.assertEqual(1, len(new_m2.evidence))
        new_evidence = new_m2.evidence[0]
        self.assertIsInstance(new_evidence, ReasonedEvidence)
        new_confidence = new_evidence.get_confidence()
        self.assertIsNotNone(new_confidence)
        self.assertEqual(1 - (1 - original_confidence) * (1 - mutation_confidence), new_confidence)
        self.assertEqual(KNOWLEDGE_MAPPING, new_evidence.justification)
