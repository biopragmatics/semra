"""Semantic Mapping Reasoning Assembler."""

import unittest
from collections import defaultdict
from itertools import islice
from operator import attrgetter
from typing import Dict, List, Optional, Tuple, Union, Iterable

import networkx as nx
import pydantic
from more_itertools import triplewise
from pydantic import Field

PREDICATE_KEY = "predicate"
EVIDENCE_KEY = "evidence"


class Reference(pydantic.BaseModel):
    """A reference to an entity in a given identifier space."""

    prefix: str
    identifier: str

    class Config:
        """Pydantic configuration for references."""

        frozen = True

    @property
    def curie(self) -> str:
        """Get the reference as a CURIE string."""
        return f"{self.prefix}:{self.identifier}"


def _get_references(n: int) -> List[Reference]:
    return [Reference(prefix="test", identifier=str(i)) for i in range(1, n + 1)]


#: A type annotation for a subject-predicate-object triple
Triple = Tuple[Reference, Reference, Reference]

"""  # --------------------------------------------------------------
CONFIGURATION

TODO: move this into a configurable class
"""  # --------------------------------------------------------------

EXACT_MATCH = Reference(prefix="skos", identifier="exactMatch")
BROAD_MATCH = Reference(prefix="skos", identifier="broadMatch")
NARROW_MATCH = Reference(prefix="skos", identifier="narrowMatch")
CLOSE_MATCH = Reference(prefix="skos", identifier="closeMatch")
# EQUIVALENT_TO = Reference(prefix="owl", identifier="equivalentTo")
FLIP = {
    BROAD_MATCH: NARROW_MATCH,
    NARROW_MATCH: BROAD_MATCH,
    EXACT_MATCH: EXACT_MATCH,
}
#: Which predicates are transitive?
TRANSITIVE = {BROAD_MATCH, NARROW_MATCH, EXACT_MATCH}
#: Which predicates are directionless
DIRECTIONLESS = {EXACT_MATCH, CLOSE_MATCH}

#: Two step chain inference rules
TWO_STEP: Dict[Tuple[Reference, Reference], Reference] = {
    (BROAD_MATCH, EXACT_MATCH): BROAD_MATCH,
    (EXACT_MATCH, BROAD_MATCH): BROAD_MATCH,
    (NARROW_MATCH, EXACT_MATCH): NARROW_MATCH,
    (EXACT_MATCH, NARROW_MATCH): NARROW_MATCH,
}


class Evidence(pydantic.BaseModel):
    """Evidence for a mapping.

    Ideally, this matches the SSSOM data model.
    """

    justification: Optional[Reference] = Field(description="A SSSOM-compliant justification")


class Mapping(pydantic.BaseModel):
    """A semantic mapping."""

    s: Reference
    p: Reference
    o: Reference
    evidence: List[Evidence] = Field(default_factory=list)

    @property
    def triple(self) -> Triple:
        """Get the mapping's core triple as a tuple."""
        return self.s, self.p, self.o

    @classmethod
    def from_triple(cls, triple: Triple, evidence: Optional[List[Evidence]] = None) -> "Mapping":
        """Instantiate a mapping from a triple."""
        s, p, o = triple
        return cls(s=s, p=p, o=o, evidence=evidence or [])


#: An index allows for the aggregation of evidences for each core triple
Index = Dict[Triple, List[Evidence]]


def get_index(mappings: List[Mapping]) -> Index:
    """Aggregate evidences for each core triple."""
    dd = defaultdict(list)
    for mapping in mappings:
        dd[mapping.triple].extend(mapping.evidence)
    return dict(dd)


def assemble_evidences(mappings: List[Mapping]) -> List[Mapping]:
    return [
        Mapping.from_triple(triple, evidence=deduplicate_evidences(evidences))
        for triple, evidences in get_index(mappings).items()
    ]


def deduplicate_evidences(evidences: List[Evidence]) -> List[Evidence]:
    return evidences  # TODO


def flip_mappings(mappings: List[Mapping]) -> List[Mapping]:
    rv = []
    for mapping in mappings:
        rv.append(mapping)
        if flipped_mapping := flip(mapping):
            rv.append(flipped_mapping)
    return rv


def flip(mapping: Mapping) -> Optional[Mapping]:
    if mapping.p not in FLIP:
        return None
    return Mapping(s=mapping.o, p=FLIP[mapping.p], o=mapping.s, evidence=mapping.evidence)


def infer(mappings: List[Mapping]) -> List[Mapping]:
    graph = graph_infer(mappings)
    return from_graph(graph)


def from_graph(graph: nx.DiGraph) -> List[Mapping]:
    rv = []
    for u, v, data in graph.edges(data=True):
        mapping = Mapping(s=u, p=data[PREDICATE_KEY], o=v, evidence=data[EVIDENCE_KEY])
        rv.append(mapping)
    return rv


def _add_to_digraph(graph: nx.DiGraph, mapping: Mapping) -> None:
    """Add a mapping as a directed edge to a directed graph."""
    graph.add_edge(
        mapping.s,
        mapping.o,
        **{PREDICATE_KEY: mapping.p, EVIDENCE_KEY: mapping.evidence},
    )


def to_graphs(mappings: Iterable[Mapping]) -> Dict[Reference, nx.DiGraph]:
    """Collect mappings into sepeate grap"""
    # Calculate graph for each edge type
    graphs = defaultdict(nx.DiGraph)
    for mapping in mappings:
        _add_to_digraph(graphs[mapping.p], mapping)
    return dict(graphs)


def _graph_process(graph: nx.DiGraph, predicate: Reference):
    if predicate not in TRANSITIVE:
        return graph
    inferred = Reference(prefix="xxx", identifier="yyy")
    tc = nx.transitive_closure(graph)
    for s, o, d in tc.edges(data=True):
        if not graph.has_edge(s, o):
            d[PREDICATE_KEY] = predicate
            d[EVIDENCE_KEY] = [Evidence(justification=inferred)]
    return tc


def graph_infer(mappings: List[Mapping]):
    graphs = to_graphs(mappings)

    # Calculate transitive closures over all graphs
    processed_graphs = [
        _graph_process(graph, predicate)
        for predicate, graph in graphs.items()
    ]

    # Union all transitive closure graphs
    graph: nx.DiGraph = nx.compose_all(processed_graphs)

    # Do two-step reasoning over this graph
    reasoned = []
    for n1, n2, d1 in graph.edges(data=True):
        predicate_1 = d1[PREDICATE_KEY]
        for _, n3, d2 in graph.edges(n2, data=True):
            p3 = TWO_STEP.get(predicate_1, d2[PREDICATE_KEY])
            if p3:
                evidence = Reference(prefix="xxx", identifier="zzz")
                reasoned.append((n1, n3, {PREDICATE_KEY: p3, EVIDENCE_KEY: [evidence]}))
    graph.add_edges_from(reasoned)
    return graph


def process(mappings: List[Mapping]):
    mappings = assemble_evidences(mappings)
    mappings = flip_mappings(mappings)
    mappings = assemble_evidences(mappings)
    mappings = infer(mappings)
    mappings = assemble_evidences(mappings)
    return mappings


def _triple_key(t: Triple):
    return t[0].curie, t[2].curie, t[1].curie


def index_str(index: Index) -> str:
    from tabulate import tabulate

    rows = []
    key = lambda pair: _triple_key(pair[0])
    for (s, p, o), evidences in sorted(index.items(), key=key):
        if not evidences:
            rows.append((s.curie, p.curie, o.curie, ""))
        else:
            first, *rest = evidences
            rows.append((s.curie, p.curie, o.curie, first))
            for r in rest:
                rows.append(("", "", "", r))
    return tabulate(rows, headers=["s", "p", "o", "ev"])


def line(*m: Reference, evidence: Optional[List[Evidence]] = None) -> List[Mapping]:
    """Create a list of mappings from a simple mappings path."""
    assert 3 <= len(m) and len(m) % 2
    return [
        Mapping(s=s, p=p, o=o, evidence=evidence or [])
        for s, p, o in islice(triplewise(m), None, None, 2)
    ]


def _exact(s, o, evidence: Optional[List[Evidence]] = None) -> Mapping:
    return Mapping(s=s, p=EXACT_MATCH, o=o, evidence=evidence or [])


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
        mapping = Mapping(s=chebi_reference, p=EXACT_MATCH, o=mesh_reference)
        new_mapping = flip(mapping)
        self.assertIsNotNone(new_mapping)
        self.assertEquals(mesh_reference, new_mapping.s)
        self.assertEquals(EXACT_MATCH, new_mapping.p)
        self.assertEquals(chebi_reference, new_mapping.o)

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
        e1 = Evidence(justification=Reference(prefix="semapv", identifier="LexicalMatching"))
        e2 = Evidence(justification=Reference(prefix="semapv", identifier="ManualMappingCuration"))
        m1 = Mapping(s=r1, p=EXACT_MATCH, o=r2, evidence=[e1])
        m2 = Mapping(s=r1, p=EXACT_MATCH, o=r2, evidence=[e2])
        index = get_index([m1, m2])
        self.assertIn(m1.triple, index)
        self.assertEqual(1, len(index))
        self.assertEqual(2, len(index[m1.triple]))
        self.assertEqual(
            {"LexicalMatching", "ManualMappingCuration"},
            {e.justification.identifier for e in index[m1.triple]},
        )

    def assert_same_triples(
        self,
        expected_mappings: List[Mapping],
        actual_mappings: Union[Index, List[Mapping]],
        msg: Optional[str] = None
    ) -> None:
        """Assert that two sets of mappings are the same."""
        if not isinstance(expected_mappings, dict):
            expected_mappings = get_index(expected_mappings)
        if not isinstance(actual_mappings, dict):
            actual_mappings = get_index(actual_mappings)

        self.assertEqual(
            self._clean_index(expected_mappings),
            self._clean_index(actual_mappings),
            msg=msg,
        )

    @staticmethod
    def _clean_index(index: Index) -> List[str]:
        triples = sorted(set(index), key=_triple_key)
        return [
            "<" + ", ".join(element.curie for element in triple) + ">"
            for triple in triples
        ]

    def test_infer_exact_match(self):
        """Test inference through the transitivity of SKOS exact matches."""
        r1, r2, r3, r4 = _get_references(4)
        m1, m2, m3 = line(r1, EXACT_MATCH, r2, EXACT_MATCH, r3, EXACT_MATCH, r4)
        m4 = _exact(r1, r3)
        m5 = _exact(r1, r4)
        m6 = _exact(r2, r4)
        m4_inv, m5_inv, m6_inv = (flip(m) for m in (m4, m5, m6))

        backwards_msg = "backwards inference is not supposed to be done here"

        index = get_index(infer([m1, m2]))
        self.assertNotIn(m4_inv.triple, index, msg=backwards_msg)

        index = get_index(infer([m1, m2, m3]))
        self.assert_same_triples([m1, m2, m3, m4, m4, m5, m6], index)
        self.assertNotIn(m4_inv.triple, index, msg=backwards_msg)
        self.assertNotIn(m5_inv.triple, index, msg=backwards_msg)
        self.assertNotIn(m6_inv.triple, index, msg=backwards_msg)

    def test_no_infer(self):
        """Test no inference happens over mixed chains of broad/narrow."""
        r1, r2, r3 = _get_references(3)
        m1, m2 = line(r1, BROAD_MATCH, r2, NARROW_MATCH, r3)
        self.assert_same_triples([m1, m2], infer([m1, m2]), msg='No inference between broad and narrow')

        m1, m2 = line(r1, NARROW_MATCH, r2, BROAD, r3)
        self.assert_same_triples([m1, m2], infer([m1, m2]), msg='No inference between broad and narrow')

    def test_infer_broad_match_1(self):
        r1, r2, r3, r4 = _get_references(4)
        m1, m2, m3 = line(r1, EXACT_MATCH, r2, BROAD_MATCH, r3, EXACT_MATCH, r4)
        m4 = Mapping(s=r1, p=BROAD_MATCH, o=r3)
        m5 = Mapping(s=r1, p=BROAD_MATCH, o=r4)
        m6 = Mapping(s=r2, p=BROAD_MATCH, o=r4)

        # Check inference over two steps
        self.assert_same_triples([m1, m2, m4], infer([m1, m2]))

        # Check inference over multiple steps
        self.assert_same_triples([m1, m2, m3, m4, m5, m6], infer([m1, m2, m3]))

    def test_infer_broad_match_2(self):
        r1, r2, r3, r4 = _get_references(4)
        m1, m2, m3 = line(r1, BROAD_MATCH, r2, EXACT_MATCH, r3, BROAD_MATCH, r4)
        m4 = Mapping(s=r1, p=BROAD_MATCH, o=r3)
        m5 = Mapping(s=r1, p=BROAD_MATCH, o=r4)
        m6 = Mapping(s=r2, p=BROAD_MATCH, o=r4)

        # Check inference over two steps
        self.assert_same_triples([m1, m2, m4], infer([m1, m2]))

        # Check inference over multiple steps
        self.assert_same_triples([m1, m2, m3, m4, m5, m6], infer([m1, m2, m3]))

    def test_infer_narrow_match(self):
        r1, r2, r3 = _get_references(3)
        m1, m2 = line(r1, EXACT_MATCH, r2, NARROW_MATCH, r3)
        m3 = Mapping(s=r1, p=NARROW_MATCH, o=r3)
        index = get_index(infer([m1, m2]))
        self.assert_same_triples([m1, m2, m3], index)

    def test_mixed_inference_1(self):
        r1, r2, r3 = _get_references(3)
        m1 = Mapping(s=r1, p=EXACT_MATCH, o=r2)
        m2 = Mapping(s=r2, p=NARROW_MATCH, o=r3)
        m3 = Mapping(s=r1, p=NARROW_MATCH, o=r3)

        m4 = Mapping(s=r2, p=EXACT_MATCH, o=r1)
        m5 = Mapping(s=r3, p=BROAD_MATCH, o=r2)
        m6 = Mapping(s=r3, p=BROAD_MATCH, o=r1)

        mappings = [m1, m2]
        mappings = flip_mappings(mappings)
        self.assert_same_triples([m1, m2, m4, m5], mappings)

        mappings = infer(mappings)
        self.assert_same_triples([m1, m2, m3, m4, m5, m6], mappings)
