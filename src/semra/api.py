"""Semantic Mapping Reasoning Assembler."""

from __future__ import annotations

import itertools as itt
import logging
import typing
import typing as t
from collections import Counter, defaultdict
from collections.abc import Iterable
from typing import cast

import networkx as nx
import pandas as pd
from tqdm.auto import tqdm

from semra.rules import (
    BROAD_MATCH,
    CHAIN_MAPPING,
    DB_XREF,
    EXACT_MATCH,
    FLIP,
    INVERSION_MAPPING,
    KNOWLEDGE_MAPPING,
    NARROW_MATCH,
)
from semra.struct import (
    Evidence,
    Mapping,
    MappingSet,
    ReasonedEvidence,
    Reference,
    SimpleEvidence,
    Triple,
    triple_key,
)

__all__ = [
    # Types
    "Index",
    "M2MIndex",
    # Constants
    "PREDICATE_KEY",
    "EVIDENCE_KEY",
    "TEST_MAPPING_SET",
    # Functions
    "get_test_reference",
    "get_test_evidence",
    "count_source_target",
    "str_source_target_counts",
    "print_source_target_counts",
    "get_index",
    "assemble_evidences",
    "infer_reversible",
    "flip",
    "to_digraph",
    "to_multidigraph",
    "from_digraph",
    "infer_chains",
    "tabulate_index",
    "infer_mutual_dbxref_mutations",
    "infer_dbxref_mutations",
    "infer_mutations",
    "keep_prefixes",
    "keep_subject_prefixes",
    "keep_object_prefixes",
    "filter_prefixes",
    "filter_self_matches",
    "filter_mappings",
    "get_many_to_many",
    "filter_many_to_many",
    "project",
    "project_dict",
    "assert_projection",
    "prioritize",
    "get_priority_reference",
    "unindex",
    "deduplicate_evidence",
    "validate_mappings",
    "summarize_prefixes",
    "filter_minimum_confidence",
    "filter_subsets",
    "count_component_sizes",
]


logger = logging.getLogger(__name__)

PREDICATE_KEY = "predicate"
EVIDENCE_KEY = "evidence"

#: An index allows for the aggregation of evidences for each core triple
Index = t.Dict[Triple, t.List[Evidence]]


def _tqdm(mappings, desc: str | None = None, *, progress: bool = True, leave: bool = True):
    return tqdm(
        mappings,
        unit_scale=True,
        unit="mapping",
        desc=desc,
        leave=leave,
        disable=not progress,
    )


#: A test mapping set that can be used in examples.
TEST_MAPPING_SET = MappingSet(name="Test Mapping Set", confidence=0.95)


# docstr-coverage: inherited
@typing.overload
def get_test_evidence(n: int) -> t.List[SimpleEvidence]: ...  # noqa:D103


# docstr-coverage: inherited
@typing.overload
def get_test_evidence(n: None) -> SimpleEvidence: ...  # noqa:D103


def get_test_evidence(n: t.Optional[int] = None) -> t.Union[SimpleEvidence, t.List[SimpleEvidence]]:
    """Get test evidence."""
    if isinstance(n, int):
        return [SimpleEvidence(mapping_set=TEST_MAPPING_SET) for _ in range(n)]
    return SimpleEvidence(mapping_set=TEST_MAPPING_SET)


# docstr-coverage: inherited
@typing.overload
def get_test_reference(n: int, prefix: str) -> t.List[Reference]: ...  # noqa:D103


# docstr-coverage: inherited
@typing.overload
def get_test_reference(n: None, prefix: str) -> Reference: ...  # noqa:D103


def get_test_reference(n: t.Optional[int] = None, prefix: str = "test") -> t.Union[Reference, t.List[Reference]]:
    """Get test reference(s)."""
    if isinstance(n, int):
        return [Reference(prefix=prefix, identifier=str(i + 1)) for i in range(n)]
    return Reference(prefix=prefix, identifier="1")


def count_source_target(mappings: Iterable[Mapping]) -> Counter[t.Tuple[str, str]]:
    """Count pairs of source/target prefixes.

    :param mappings: An iterable of mappings
    :return:
        A counter whose keys are pairs of source prefixes and target prefixes
        appearing in the mappings

    >>> from semra import Mapping, Reference, EXACT_MATCH
    >>> r1 = Reference(prefix="p1", identifier="1")
    >>> r2 = Reference(prefix="p2", identifier="a")
    >>> m1 = Mapping(s=r1, p=EXACT_MATCH, o=r2)
    >>> count_source_target(mappings)
    Counter({('p1', 'p2'): 1})
    """
    return Counter((s.prefix, o.prefix) for s, _, o in get_index(mappings))


def str_source_target_counts(mappings: Iterable[Mapping], minimum: int = 0) -> str:
    """Create a table of counts of source/target prefix via :mod:`tabulate`.

    :param mappings: An iterable of mappings
    :param minimum: The minimum count to display in the table. Defaults to zero,
        which displays all source/target prefix pairs.
    :return:
        A table representing the counts for each source/target prefix pair.

    .. seealso:: This table is generated with :func:`count_source_target`
    """
    from tabulate import tabulate

    so_prefix_counter = count_source_target(mappings)
    return tabulate(
        [(s, o, c) for (s, o), c in so_prefix_counter.most_common() if c > minimum],
        headers=["source prefix", "target prefix", "count"],
        tablefmt="github",
    )


def print_source_target_counts(mappings: Iterable[Mapping], minimum: int = 0) -> None:
    """Print the counts of source/target prefixes.

    :param mappings: An iterable of mappings
    :param minimum: The minimum count to display in the table. Defaults to zero,
        which displays all source/target prefix pairs.

    .. seealso:: This table is generated with :func:`str_source_target_counts`
    """
    print(str_source_target_counts(mappings=mappings, minimum=minimum))  # noqa:T201


def get_index(mappings: Iterable[Mapping], *, progress: bool = True, leave: bool = False) -> Index:
    """Aggregate and deduplicate evidences for each core triple."""
    dd: t.DefaultDict[Triple, t.List[Evidence]] = defaultdict(list)
    for mapping in _tqdm(mappings, desc="Indexing mappings", progress=progress, leave=leave):
        dd[mapping.triple].extend(mapping.evidence)
    return {triple: deduplicate_evidence(evidence) for triple, evidence in dd.items()}


def assemble_evidences(mappings: t.List[Mapping], *, progress: bool = True) -> t.List[Mapping]:
    """Assemble evidences.

    More specifically, this aggregates evidences for all subject-predicate-object triples
    into a single :class:`semra.Mapping` instance.

    :param mappings: An iterable of mappings
    :param progress: Should a progress bar be shown? Defaults to true.
    :returns: A processed list of mappings, that is guaranteed to have
        exactly 1 Mapping object for each subject-predicate-object triple.
        Note that if the predicate is different, evidences are not assembled
        into the same Mapping object.

    >>> from semra import Mapping, Reference, EXACT_MATCH
    >>> from semra.api import get_test_evidence, get_test_reference
    >>> r1 = get_test_reference(prefix="p1")
    >>> r2 = get_test_reference(prefix="p2")
    >>> e1, e2 = get_test_evidence(2)
    >>> m1 = Mapping(s=r1, p=EXACT_MATCH, o=r2, evidence=[e1])
    >>> m2 = Mapping(s=r1, p=EXACT_MATCH, o=r2, evidence=[e2])
    >>> m = assemble_evidences([m1, m2])
    >>> assert m == [Mapping(s=r1, p=EXACT_MATCH, o=r2, evidence=[e1, e2])]
    """
    index = get_index(mappings, progress=progress)
    return unindex(index, progress=progress)


def infer_reversible(mappings: t.Iterable[Mapping], *, progress: bool = True) -> t.List[Mapping]:
    """Extend the mapping list with flipped mappings.

    :param mappings: An iterable of mappings
    :param progress: Should a progress bar be shown? Defaults to true.
    :returns:
        A list where if a mapping can be flipped (i.e., :func:`flip`), a flipped
        mapping is added. Flipped mappings contain reasoned evidence
        :class:`ReasonedEvidence` objects that point to the mapping from which
        the evidence was derived.

    Flipping a mapping means switching the subject and object, then modifying the
    predicate as follows:

    1. Broad becomes narrow
    2. Narrow becomes broad
    3. Exact and close mappings remain the same, since they're reflexive

    This is configured in the :data:`semra.rules.FLIP` dictionary.

    >>> from semra import Mapping, Reference, EXACT_MATCH, SimpleEvidence
    >>> from semra.api import get_test_evidence, get_test_reference
    >>> r1 = get_test_reference(prefix="p1")
    >>> r2 = get_test_reference(prefix="p2")
    >>> e1 = get_test_evidence()
    >>> m1 = Mapping(s=r1, p=EXACT_MATCH, o=r2, evidence=[e1])
    >>> mappings = list(infer_reversible([m1]))
    >>> len(mappings)
    2
    >>> mappings[0] == m1

    .. warning::

        This operation does not "assemble", meaning if you had existing evidence
        for an inverse mapping, they will be seperate. Therefore, you can chain
        it with the :func:`assemble_evidences` operation:

        >>> from semra import Mapping, Reference, EXACT_MATCH
        >>> from semra.api import get_test_evidence
        >>> from semra.api import get_test_evidence, get_test_reference
        >>> r1 = get_test_reference(prefix="p1")
        >>> r2 = get_test_reference(prefix="p2")
        >>> e1, e2 = get_test_evidence(2)
        >>> m1 = Mapping(s=r1, p=EXACT_MATCH, o=r2, evidence=[e1])
        >>> m2 = Mapping(s=r2, p=EXACT_MATCH, o=r1, evidence=[e2])
        >>> mappings = list(infer_reversible([m1, m2]))
        >>> len(mappings)
        3
        >>> mappings = assemble_evidences(mappings)
        >>> len(mappings)
        2

    """
    rv = []
    for mapping in _tqdm(mappings, desc="Infer reverse", progress=progress):
        rv.append(mapping)
        if flipped_mapping := flip(mapping):
            rv.append(flipped_mapping)
    return rv


# TODO infer negative mappings for exact match from narrow/broad match


def flip(mapping: Mapping) -> Mapping | None:
    """Flip a mapping, if the relation is configured with an inversion.

    :param mapping: An input mapping
    :return:
        If the input mapping's predicate is configured with an inversion
        (e.g., broad match is configured by default to invert to narrow
        match), a new mapping is returned with the subject and object swapped,
        with the inverted predicate, and with a "mutated" evidence to
        track original provenance. If the mapping's predicate is not configured
        with an inversion (e.g., for practical purposes, regular dbrefs and
        close matches are not configured to invert), then None is returned
    """
    if (p := FLIP.get(mapping.p)) is None:
        return None
    return Mapping(
        s=mapping.o,
        p=p,
        o=mapping.s,
        evidence=[ReasonedEvidence(justification=INVERSION_MAPPING, mappings=[mapping])],
    )


def to_digraph(mappings: t.Iterable[Mapping]) -> nx.DiGraph:
    """Convert mappings into a simple directed graph data model.

    :param mappings: An iterable of mappings
    :returns: A directed graph in which the nodes are
        :class:`curies.Reference` objects. The predicate
        is put under the :data:`PREDICATE_KEY` key in the
        edge data and the evidences are put under the
        :data:`EVIDENCE_KEY` key in the edge data.

    .. warning::

        This function makes two assumptions:

        1. The graph has already been assembled using :func:`assemble_evidences`
        2. That only one predicate is used in the graph.

        In order to support multiple predicate types, this would have to be
        a :class:`networkx.MultiDiGraph` and use
        ``graph.add_edge(mappings.s, mapping.o, key=mapping.p, **{EVIDENCE_KEY: mapping.evidence})``
    """
    graph = nx.DiGraph()
    for mapping in mappings:
        graph.add_edge(
            mapping.s,
            mapping.o,
            #  TODO group all predicates then evidences
            # **{PREDICATE_KEY: mapping.p, EVIDENCE_KEY: mapping.evidence},
        )
    return graph


def iter_components(mappings: t.Iterable[Mapping]) -> t.Iterable[t.Set[Reference]]:
    """Iterate over connected components in the multidigraph view over the mappings."""
    graph = to_digraph(mappings)
    return nx.weakly_connected_components(graph)


def to_multidigraph(mappings: t.Iterable[Mapping], *, progress: bool = False) -> nx.MultiDiGraph:
    """Convert mappings into a multi directed graph data model.

    :param mappings: An iterable of mappings
    :param progress: Should a progress bar be shown?
    :returns: A directed graph in which the nodes are
        :class:`curies.Reference` objects. The predicate
        is put under the :data:`PREDICATE_KEY` key in the
        edge data and the evidences are put under the
        :data:`EVIDENCE_KEY` key in the edge data.

    .. warning::

        This function makes the following assumptions:

        1. The graph has already been assembled using :func:`assemble_evidences`

    """
    graph = nx.MultiDiGraph()
    for mapping in _tqdm(mappings, progress=progress):
        graph.add_edge(
            mapping.s,
            mapping.o,
            key=mapping.p,
            **{EVIDENCE_KEY: mapping.evidence},
        )
    return graph


def from_digraph(graph: nx.DiGraph) -> t.List[Mapping]:
    """Extract mappings from a simple directed graph data model."""
    return [_from_digraph_edge(graph, s, o) for s, o in graph.edges()]


def _from_digraph_edge(graph: nx.Graph, s: Reference, o: Reference) -> Mapping:
    data = graph[s][o]
    return Mapping(s=s, p=data[PREDICATE_KEY], o=o, evidence=data[EVIDENCE_KEY])


def _reason_multiple_predicates(predicates: t.Iterable[Reference]) -> Reference | None:
    """Return a single reasoned predicate based on a set, if possible.

    :param predicates: A collection of predicates
    :return:
        A single predicate that represents the set, if possible

        For example, if a predicate set with exact + broad are given, then
        the most specific possible is exact. If a predicate contains
        exact, broad, and narrow, then no reasoning can be done and None is returned.
    """
    predicate_set = set(predicates)
    if predicate_set == {EXACT_MATCH}:
        return EXACT_MATCH
    if predicate_set == {BROAD_MATCH} or predicate_set == {EXACT_MATCH, BROAD_MATCH}:  # noqa:PLR1714
        return BROAD_MATCH
    if predicate_set == {NARROW_MATCH} or predicate_set == {EXACT_MATCH, NARROW_MATCH}:  # noqa:PLR1714
        return NARROW_MATCH
    return None


def infer_chains(
    mappings: t.List[Mapping],
    *,
    backwards: bool = True,
    progress: bool = True,
    cutoff: int = 5,
    minimum_component_size: int = 2,
    maximum_component_size: int = 100,
) -> t.List[Mapping]:
    """Apply graph-based reasoning over mapping chains to infer new mappings.

    :param mappings: A list of input mappings
    :param backwards: Should inference be done in reverse?
    :param progress: Should a progress bar be shown? Defaults to true.
    :param cutoff: What's the maximum length path to infer over?
    :param minimum_component_size: The smallest size of a component to consider, defaults to 2
    :param maximum_component_size: The smallest size of a component to consider, defaults to 100.
        Components that are very large (i.e., much larger than the number of target prefixes)
        likely are the result of many broad/narrow mappings
    :return: The list of input mappings _plus_ inferred mappings
    """
    mappings = assemble_evidences(mappings, progress=progress)
    graph = to_multidigraph(mappings)
    new_mappings = []

    components = sorted(
        (
            component
            for component in nx.weakly_connected_components(graph)
            if minimum_component_size < len(component) <= maximum_component_size
        ),
        key=len,
        reverse=True,
    )
    it = tqdm(components, unit="component", desc="Inferring chains", unit_scale=True, disable=not progress)
    for _i, component in enumerate(it):
        sg: nx.MultiDiGraph = graph.subgraph(component).copy()
        sg_len = sg.number_of_nodes()
        it.set_postfix(size=sg_len)
        inner_it = tqdm(
            itt.combinations(sg, 2),
            total=sg_len * (sg_len - 1) // 2,
            unit_scale=True,
            disable=not progress,
            unit="edge",
            leave=False,
        )
        for s, o in inner_it:
            if sg.has_edge(s, o):  # do not overwrite existing mappings
                continue
            # TODO there has to be a way to reimplement transitive closure to handle this
            # nx.shortest_path(sg, s, o)
            predicate_evidence_dict: t.DefaultDict[Reference, t.List[Evidence]] = defaultdict(list)
            for path in nx.all_simple_edge_paths(sg, s, o, cutoff=cutoff):
                if _path_has_prefix_duplicates(path):
                    continue
                predicates = [k for _u, _v, k in path]
                p = _reason_multiple_predicates(predicates)
                if p is not None:
                    evidence = ReasonedEvidence(
                        justification=CHAIN_MAPPING,
                        mappings=[
                            Mapping(
                                s=path_s,
                                o=path_o,
                                p=path_p,
                                evidence=graph[path_s][path_o][path_p][EVIDENCE_KEY],
                            )
                            for path_s, path_o, path_p in path
                        ],
                        # TODO add confidence that's inversely proportional to sg_len, i.e.
                        # larger components should return less confident mappings
                    )
                    predicate_evidence_dict[p].append(evidence)

            for p, evidences in predicate_evidence_dict.items():
                new_mappings.append(Mapping(s=s, p=p, o=o, evidence=evidences))
                if backwards:
                    new_mappings.append(Mapping(o=s, s=o, p=FLIP[p], evidence=evidences))

    return [*mappings, *new_mappings]


def _path_has_prefix_duplicates(path) -> bool:
    """Return if the path has multiple unique."""
    elements = set()
    for u, v, _ in path:
        elements.add(u)
        elements.add(v)
    counter = Counter(element.prefix for element in elements)
    return any(v > 1 for v in counter.values())


def tabulate_index(index: Index) -> str:
    """Create a table of all mappings contained in an index.

    :param index: An index of mappings - a dictionary
        whose keys are subject-predicate-object tuples
        and values are lists of associated evidence (pre-deduplicated)
    :return:
        A table with four columns:

        1. Source
        2. Predicate
        3. Object
        4. Evidences
    """
    from tabulate import tabulate

    rows: t.List[t.Tuple[str, str, str, str]] = []
    for (s, p, o), evidences in sorted(index.items(), key=lambda pair: triple_key(pair[0])):
        if not evidences:
            rows.append((s.curie, p.curie, o.curie, ""))
        else:
            first, *rest = evidences
            rows.append((s.curie, p.curie, o.curie, str(first)))
            for r in rest:
                rows.append(("", "", "", str(r)))
    return tabulate(rows, headers=["s", "p", "o", "ev"], tablefmt="github")


def infer_mutual_dbxref_mutations(
    mappings: Iterable[Mapping],
    prefixes: set[str],
    confidence: float | None = None,
    *,
    progress: bool = False,
) -> t.List[Mapping]:
    """Upgrade database cross-references into exact matches for the given pairs.

    :param mappings: A list of mappings
    :param prefixes: A dictionary of source/target prefix pairs to the confidence of upgrading dbxrefs.
        If giving a collection of pairs, will use the ``confidence`` value as given.
    :param confidence: The default confidence to be used if ``pairs`` is given as a collection.
        Defaults to 0.7
    :param progress: Should a progress bar be shown? Defaults to true.
    :return: A new list of mappings containing upgrades

    In the following example, we use four different terms for
    *cranioectodermal dysplasia* from the Disease Ontology (DOID), Medical Subject Headings (MeSH),
    and Unified Medical Language System (UMLS). We use the prior knowledge
    that there's a high confidence that dbxrefs from DOID to MeSH are actually exact matches. This lets us infer
    ``m3`` from ``m1``.  We don't make any assertions about DOID-UMLS or MeSH-UMLS mappings here,
    so the example mapping ``m2`` comes along for the ride.

    >>> from semra import DB_XREF, EXACT_MATCH, Reference, NARROW_MATCH
    >>> curies = "DOID:0050577", "mesh:C562966", "umls:C4551571"
    >>> r1, r2, r3, r4 = map(Reference.from_curie, curies)
    >>> m1 = Mapping.from_triple((r1, DB_XREF, r2))
    >>> m2 = Mapping.from_triple((r2, DB_XREF, r3))
    >>> mappings = [m1, m2, m3]
    >>> pairs = {("DOID", "mesh"): 0.99}
    >>> m3 = Mapping.from_triple((r1, EXACT_MATCH, r2))  # this is what we are inferring
    >>> assert infer_dbxref_mutations(mappings, pairs) == [m1, m3, m2]

    This function is a thin wrapper around :func:`infer_mutations` where :data:`semra.DB_XREF`
    is used as the "old" predicated and :data:`semra.EXACT_MATCH` is used as the "new" predicate.
    """
    pairs = {
        (subject_prefix, object_prefix)
        for subject_prefix, object_prefix in itt.product(prefixes, repeat=2)
        if subject_prefix != object_prefix
    }
    return infer_dbxref_mutations(mappings, pairs=pairs, confidence=confidence, progress=progress)


def infer_dbxref_mutations(
    mappings: Iterable[Mapping],
    pairs: t.Dict[t.Tuple[str, str], float] | Iterable[t.Tuple[str, str]],
    confidence: float | None = None,
    progress: bool = False,
) -> t.List[Mapping]:
    """Upgrade database cross-references into exact matches for the given pairs.

    :param mappings: A list of mappings
    :param pairs: A dictionary of source/target prefix pairs to the confidence of upgrading dbxrefs.
        If giving a collection of pairs, will use the ``confidence`` value as given.
    :param confidence: The default confidence to be used if ``pairs`` is given as a collection.
        Defaults to 0.7
    :param progress: Should a progress bar be shown? Defaults to true.
    :return: A new list of mappings containing upgrades

    In the following example, we use four different terms for
    *cranioectodermal dysplasia* from the Disease Ontology (DOID), Medical Subject Headings (MeSH),
    and Unified Medical Language System (UMLS). We use the prior knowledge
    that there's a high confidence that dbxrefs from DOID to MeSH are actually exact matches. This lets us infer
    ``m3`` from ``m1``.  We don't make any assertions about DOID-UMLS or MeSH-UMLS mappings here,
    so the example mapping ``m2`` comes along for the ride.

    >>> from semra import DB_XREF, EXACT_MATCH, Reference, NARROW_MATCH
    >>> curies = "DOID:0050577", "mesh:C562966", "umls:C4551571"
    >>> r1, r2, r3, r4 = (Reference.from_curie(c) for c in curies)
    >>> m1 = Mapping.from_triple((r1, DB_XREF, r2))
    >>> m2 = Mapping.from_triple((r2, DB_XREF, r3))
    >>> mappings = [m1, m2, m3]
    >>> pairs = {("DOID", "mesh"): 0.99}
    >>> m3 = Mapping.from_triple((r1, EXACT_MATCH, r2))  # this is what we are inferring
    >>> assert infer_dbxref_mutations(mappings, pairs) == [m1, m3, m2]

    This function is a thin wrapper around :func:`infer_mutations` where :data:`semra.DB_XREF`
    is used as the "old" predicated and :data:`semra.EXACT_MATCH` is used as the "new" predicate.
    """
    if confidence is None:
        confidence = 0.7
    if not isinstance(pairs, dict):
        pairs = {pair: confidence for pair in pairs}
    return infer_mutations(
        mappings,
        pairs=pairs,
        old_predicate=DB_XREF,
        new_predicate=EXACT_MATCH,
        progress=progress,
    )


def infer_mutations(
    mappings: Iterable[Mapping],
    pairs: t.Dict[t.Tuple[str, str], float],
    old_predicate: Reference,
    new_predicate: Reference,
    *,
    progress: bool = False,
) -> t.List[Mapping]:
    """Infer mappings with alternate predicates for the given prefix pairs.

    :param mappings: Mappings to infer from
    :param pairs: A dictionary of pairs of (subject prefix, object prefix) to the confidence
        of inference
    :param old_predicate: The predicate on which inference should be done
    :param new_predicate: The predicate to get inferred
    :param progress: Should a progress bar be shown? Defaults to true.
    :returns: A list of all old mapping plus inferred ones interspersed.

    In the following example, we use three different terms for
    *cranioectodermal dysplasia* from the Disease Ontology (DOID), Medical Subject Headings (MeSH),
    and Unified Medical Language System (UMLS). We use the prior knowledge that there's a high
    confidence that dbxrefs from DOID to MeSH are actually exact matches. This lets us infer
    ``m3`` from ``m1``.  We don't make any assertions about DOID-UMLS or MeSH-UMLS mappings here,
    so the example mapping ``m2`` comes along for the ride.

    >>> from semra import DB_XREF, EXACT_MATCH, Reference
    >>> curies = "DOID:0050577", "mesh:C562966", "umls:C4551571"
    >>> r1, r2, r3 = (Reference.from_curie(c) for c in curies)
    >>> m1 = Mapping.from_triple((r1, DB_XREF, r2))
    >>> m2 = Mapping.from_triple((r2, DB_XREF, r3))
    >>> mappings = [m1, m2]
    >>> pairs = {("DOID", "mesh"): 0.99}
    >>> m3 = Mapping.from_triple((r1, EXACT_MATCH, r2))  # this is what we are inferring
    >>> assert infer_mutations(mappings, pairs, DB_XREF, EXACT_MATCH) == [m1, m3, m2]
    """
    rv = []
    for mapping in _tqdm(mappings, desc="Adding mutated predicates", progress=progress):
        rv.append(mapping)
        if mapping.p != old_predicate:
            continue
        confidence_factor = pairs.get((mapping.s.prefix, mapping.o.prefix))
        if confidence_factor is None:
            # This means that there was no explicit confidence set for the
            # subject/object prefix pair, meaning it wasn't asked to be inferred
            continue
        inferred_mapping = Mapping(
            s=mapping.s,
            p=new_predicate,
            o=mapping.o,
            evidence=[
                ReasonedEvidence(
                    justification=KNOWLEDGE_MAPPING,
                    mappings=[mapping],
                    confidence_factor=confidence_factor,
                )
            ],
        )
        rv.append(inferred_mapping)
    return rv


def keep_prefixes(mappings: Iterable[Mapping], prefixes: Iterable[str], *, progress: bool = True) -> t.List[Mapping]:
    """Filter out mappings whose subject or object are not in the given list of prefixes.

    :param mappings: A list of mappings
    :param prefixes: A set of prefixes to use for filtering the mappings
    :param progress: Should a progress bar be shown? Defaults to true.
    :return: A subset of the original mappings whose subject and object are both in the given prefix list

    >>> from semra import DB_XREF, EXACT_MATCH, Reference
    >>> curies = "DOID:0050577", "mesh:C562966", "umls:C4551571"
    >>> r1, r2, r3 = (Reference.from_curie(c) for c in curies)
    >>> m1 = Mapping.from_triple((r1, DB_XREF, r2))
    >>> m2 = Mapping.from_triple((r2, DB_XREF, r3))
    >>> m3 = Mapping.from_triple((r1, DB_XREF, r3))
    >>> assert keep_prefixes([m1, m2, m3], {"DOID", "mesh"}) == [m1]
    """
    prefixes = set(prefixes)
    return [
        mapping
        for mapping in _tqdm(mappings, desc=f"Keeping from {len(prefixes)} prefixes", progress=progress)
        if mapping.s.prefix in prefixes and mapping.o.prefix in prefixes
    ]


def keep_subject_prefixes(
    mappings: Iterable[Mapping], prefixes: str | Iterable[str], *, progress: bool = True
) -> t.List[Mapping]:
    """Filter out mappings whose subjects are not in the given list of prefixes.

    :param mappings: A list of mappings
    :param prefixes: A set of prefixes to use for filtering the mappings' subjects
    :param progress: Should a progress bar be shown? Defaults to true.
    :return: A subset of the original mappings whose subjects are in the given prefix list

    >>> from semra import DB_XREF, EXACT_MATCH, Reference
    >>> curies = "DOID:0050577", "mesh:C562966", "umls:C4551571"
    >>> r1, r2, r3 = (Reference.from_curie(c) for c in curies)
    >>> m1 = Mapping.from_triple((r1, DB_XREF, r2))
    >>> m2 = Mapping.from_triple((r2, DB_XREF, r3))
    >>> m3 = Mapping.from_triple((r1, DB_XREF, r3))
    >>> assert keep_prefixes([m1, m2, m3], {"DOID"}) == [m1, m3]
    """
    prefixes = {prefixes} if isinstance(prefixes, str) else set(prefixes)
    return [
        mapping
        for mapping in _tqdm(mappings, desc="Filtering subject prefixes", progress=progress)
        if mapping.s.prefix in prefixes
    ]


def keep_object_prefixes(
    mappings: Iterable[Mapping], prefixes: str | Iterable[str], *, progress: bool = True
) -> t.List[Mapping]:
    """Filter out mappings whose objects are not in the given list of prefixes.

    :param mappings: A list of mappings
    :param prefixes: A set of prefixes to use for filtering the mappings' objects
    :param progress: Should a progress bar be shown? Defaults to true.
    :return: A subset of the original mappings whose objects are in the given prefix list

    >>> from semra import DB_XREF, EXACT_MATCH, Reference
    >>> curies = "DOID:0050577", "mesh:C562966", "umls:C4551571"
    >>> r1, r2, r3 = (Reference.from_curie(c) for c in curies)
    >>> m1 = Mapping.from_triple((r1, DB_XREF, r2))
    >>> m2 = Mapping.from_triple((r2, DB_XREF, r3))
    >>> m3 = Mapping.from_triple((r1, DB_XREF, r3))
    >>> assert keep_prefixes([m1, m2, m3], {"mesh"}) == [m1]
    """
    prefixes = {prefixes} if isinstance(prefixes, str) else set(prefixes)
    return [
        mapping
        for mapping in _tqdm(mappings, desc="Filtering object prefixes", progress=progress)
        if mapping.o.prefix in prefixes
    ]


def filter_prefixes(mappings: Iterable[Mapping], prefixes: Iterable[str], *, progress: bool = True) -> t.List[Mapping]:
    """Filter out mappings whose subject or object are in the given list of prefixes."""
    prefixes = set(prefixes)
    return [
        mapping
        for mapping in _tqdm(mappings, desc=f"Filtering out {len(prefixes)} prefixes", progress=progress)
        if mapping.s.prefix not in prefixes and mapping.o.prefix not in prefixes
    ]


def filter_self_matches(mappings: Iterable[Mapping], *, progress: bool = True) -> t.List[Mapping]:
    """Filter out mappings within the same resource."""
    return [
        mapping
        for mapping in _tqdm(mappings, desc="Filtering out self-matches", progress=progress)
        if mapping.s.prefix != mapping.o.prefix
    ]


def filter_mappings(
    mappings: t.List[Mapping], skip_mappings: t.List[Mapping], *, progress: bool = True
) -> t.List[Mapping]:
    """Filter out mappings in the second set from the first set."""
    skip_triples = {skip_mapping.triple for skip_mapping in skip_mappings}
    return [
        mapping
        for mapping in _tqdm(mappings, desc="Filtering mappings", progress=progress)
        if mapping.triple not in skip_triples
    ]


#: A multi-leveled nested dictionary that represents many-to-many mappings.
#: The first key is subject/object pairs, the second key is either a subject identifier or object identifier,
#: the last key is the opposite object or subject identifier, and the values are a list of mappings.
#:
#: This data structure can be used to index either forward or backwards mappings,
#: as done inside :func:`get_many_to_many`
M2MIndex = t.DefaultDict[t.Tuple[str, str], t.DefaultDict[str, t.DefaultDict[str, t.List[Mapping]]]]


def get_many_to_many(mappings: t.List[Mapping]) -> t.List[Mapping]:
    """Get many-to-many mappings, disregarding predicate type."""
    forward: M2MIndex = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    backward: M2MIndex = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    for mapping in mappings:
        forward[mapping.s.prefix, mapping.o.prefix][mapping.s.identifier][mapping.o.identifier].append(mapping)
        backward[mapping.s.prefix, mapping.o.prefix][mapping.o.identifier][mapping.s.identifier].append(mapping)

    index: t.DefaultDict[Triple, t.List[Evidence]] = defaultdict(list)
    for preindex in [forward, backward]:
        for d1 in preindex.values():
            for d2 in d1.values():
                if len(d2) > 1:  # means there are multiple identifiers mapped
                    for mapping in itt.chain.from_iterable(d2.values()):
                        index[mapping.triple].extend(mapping.evidence)

    # this is effectively the same as :func:`unindex` except the deduplicate_evidence is called
    # explicitly
    rv = [Mapping.from_triple(triple, deduplicate_evidence(evidence)) for triple, evidence in index.items()]
    return rv


def filter_many_to_many(mappings: t.List[Mapping], *, progress: bool = True) -> t.List[Mapping]:
    """Filter out many to many mappings."""
    skip_mappings = get_many_to_many(mappings)
    return filter_mappings(mappings, skip_mappings, progress=progress)


def project(
    mappings: t.List[Mapping],
    source_prefix: str,
    target_prefix: str,
    *,
    return_sus: bool = False,
    progress: bool = False,
) -> t.List[Mapping] | t.Tuple[t.List[Mapping], t.List[Mapping]]:
    """Ensure that each identifier only appears as the subject of one mapping."""
    mappings = keep_subject_prefixes(mappings, source_prefix, progress=progress)
    mappings = keep_object_prefixes(mappings, target_prefix, progress=progress)
    m2m_mappings = get_many_to_many(mappings)
    mappings = filter_mappings(mappings, m2m_mappings, progress=progress)
    mappings = assemble_evidences(mappings, progress=progress)
    if return_sus:
        return mappings, m2m_mappings
    return mappings


def project_dict(mappings: t.List[Mapping], source_prefix: str, target_prefix: str) -> t.Dict[str, str]:
    """Get a dictionary from source identifiers to target identifiers."""
    mappings = cast(t.List[Mapping], project(mappings, source_prefix, target_prefix))
    return {mapping.s.identifier: mapping.o.identifier for mapping in mappings}


def assert_projection(mappings: t.List[Mapping]) -> None:
    """Raise an exception if any entities appear as the subject in multiple mappings."""
    counter = Counter(m.s for m in mappings)
    counter = Counter({k: v for k, v in counter.items() if v > 1})
    if not counter:
        return
    raise ValueError(
        f"Some subjects appear in multiple mappings, therefore this is not a "
        f"valid projection. Showing top 5: {counter.most_common(20)}"
    )


def prioritize(mappings: t.List[Mapping], priority: t.List[str]) -> t.List[Mapping]:
    """Get a priority star graph.

    :param mappings: An iterable of mappings
    :param priority: A priority list of prefixes, where earlier in the list means the priority is higher
    :return:
        A list of mappings representing a "prioritization", meaning that each element only
        appears as subject once. This condition means that the prioritization mapping can be applied
        to upgrade any reference to a "canonical" reference.

    This algorithm works in the following way

    1. Get the subset of exact matches from the input mapping list
    2. Convert the exact matches to an undirected mapping graph
    3. Extract connected components
    4. For each component
        1. Get the "priority" reference using :func:`get_priority_reference`
        2. Construct new mappings where all references in the component are the subject
           and the priority reference is the object (skip the self mapping)
    """
    original_mappings = len(mappings)
    mappings = [m for m in mappings if m.p == EXACT_MATCH]
    exact_mappings = len(mappings)

    graph = to_digraph(mappings).to_undirected()
    rv: t.List[Mapping] = []
    for component in tqdm(nx.connected_components(graph), unit="component", unit_scale=True):
        o = get_priority_reference(component, priority)
        if o is None:
            continue
        rv.extend(
            _from_digraph_edge(graph, s, o)
            # TODO should this work even if s-o edge not exists?
            #  can also do "inference" here, but also might be
            #  because of negative edge filtering
            for s in component
            if s != o and graph.has_edge(s, o)
        )

    # sort such that the mappings are ordered by object by priority order
    # then identifier of object, then subject prefix in alphabetical order
    pos = {prefix: i for i, prefix in enumerate(priority)}
    rv = sorted(rv, key=lambda m: (pos[m.o.prefix], m.o.identifier, m.s.prefix, m.s.identifier))

    end_mappings = len(rv)
    logger.info(f"Prioritized from {original_mappings:,} original ({exact_mappings:,} exact) to {end_mappings:,}")
    return rv


def get_priority_reference(component: t.Iterable[Reference], priority: t.List[str]) -> t.Optional[Reference]:
    """Get the priority reference from a component.

    :param component: A set of references with the pre-condition that they're all "equivalent"
    :param priority: A priority list of prefixes, where earlier in the list means the priority is higher
    :returns:
        Returns the reference with the prefix that has the highest priority.
        If multiple references have the highest priority prefix, returns the first one encountered.
        If none have a priority prefix, return None.

    >>> from curies import Reference
    >>> curies = ["DOID:0050577", "mesh:C562966", "umls:C4551571"]
    >>> references = [Reference.from_curie(curie) for curie in curies]
    >>> get_priority_reference(references, ["mesh", "umls"])
    'mesh:C562966'
    >>> get_priority_reference(references, ["doid", "mesh", "umls"])
    'DOID:0050577'
    >>> get_priority_reference(references, ["hpo", "ordo", "symp"])

    """
    prefix_to_references = defaultdict(list)
    for reference in component:
        prefix_to_references[reference.prefix].append(reference)
    for prefix in priority:
        references = prefix_to_references.get(prefix, [])
        if not references:
            continue
        if len(references) == 1:
            return references[0]
        # TODO multiple - I guess let's just return the first
        logger.debug("multiple references for %s", prefix)
        return references[0]
    # nothing found in priority, don't return at all.
    return None


def unindex(index: Index, *, progress: bool = True) -> t.List[Mapping]:
    """Convert a mapping index into a list of mapping objects.

    :param index: A mapping from subject-predicate-object triples to lists of evidence objects
    :param progress: Should a progress bar be shown? Defaults to true.
    :returns: A list of mapping objects

    In the following example, a very simple index for a single mapping
    is used to reconstruct a mapping list.

    >>> from semra.api import get_test_reference, get_test_evidence, unindex
    >>> s, p, o = get_test_reference(3)
    >>> e1 = get_test_evidence()
    >>> index = {(s, p, o): [e1]}
    >>> assert unindex(index) == [Mapping(s=s, p=p, o=o, evidence=[e1])]
    """
    return [
        Mapping.from_triple(triple, evidence=evidence)
        for triple, evidence in _tqdm(index.items(), desc="Unindexing mappings", progress=progress)
    ]


def deduplicate_evidence(evidence: t.List[Evidence]) -> t.List[Evidence]:
    """Deduplicate a list of evidences based on their "key" function."""
    d = {e.key(): e for e in evidence}
    return list(d.values())


def validate_mappings(mappings: t.List[Mapping], *, progress: bool = True) -> None:
    """Validate mappings against the Bioregistry and raise an error on the first invalid."""
    import bioregistry

    for mapping in tqdm(mappings, desc="Validating mappings", unit_scale=True, unit="mapping", disable=not progress):
        if bioregistry.normalize_prefix(mapping.s.prefix) != mapping.s.prefix:
            raise ValueError(f"invalid subject prefix.\n\nMapping: {mapping}\n\nSubject:{mapping.s}.")
        if bioregistry.normalize_prefix(mapping.o.prefix) != mapping.o.prefix:
            raise ValueError(f"invalid object prefix: {mapping}.")
        if not bioregistry.is_valid_identifier(mapping.s.prefix, mapping.s.identifier):
            raise ValueError(
                f"Invalid mapping subject."
                f"\n\nMapping:{mapping}."
                f"\n\nSubject: {mapping.s}"
                f"\n\nUse regex {bioregistry.get_pattern(mapping.s.prefix)}"
            )
        if ":" in mapping.s.identifier:
            raise ValueError(f"banana in mapping subject: {mapping}")
        if not bioregistry.is_valid_identifier(mapping.o.prefix, mapping.o.identifier):
            raise ValueError(
                f"Invalid mapping object."
                f"\n\nMapping:{mapping}."
                f"\n\nObject: {mapping.o}"
                f"\n\nUse regex {bioregistry.get_pattern(mapping.o.prefix)}"
            )
        if ":" in mapping.o.identifier:
            raise ValueError(f"banana in mapping object: {mapping}")


def summarize_prefixes(mappings: t.List[Mapping]) -> pd.DataFrame:
    """Get a dataframe summarizing the prefixes appearing in the mappings."""
    import bioregistry

    prefixes = set(itt.chain.from_iterable((m.o.prefix, m.s.prefix) for m in mappings))
    return pd.DataFrame(
        [
            (
                prefix,
                bioregistry.get_name(prefix),
                bioregistry.get_homepage(prefix),
                bioregistry.get_description(prefix),
            )
            for prefix in sorted(prefixes)
        ],
        columns=["prefix", "name", "homepage", "description"],
    ).set_index("prefix")


def filter_minimum_confidence(mappings: Iterable[Mapping], cutoff: float = 0.7) -> Iterable[Mapping]:
    """Filter mappings below a given confidence."""
    for mapping in mappings:
        try:
            confidence = mapping.get_confidence()
        except ValueError:
            continue
        if confidence >= cutoff:
            yield mapping


def hydrate_subsets(subset_configuration: t.Mapping[str, t.Collection[str]]) -> t.Mapping[str, t.Collection[str]]:
    """Convert a subset configuration dictionary into a subset artifact.

    :param subset_configuration: A dictionary of prefixes to sets of parent terms
    :return: A dictionary that uses the is-a hierarchy within the resources to get full term lists
    :raises ValueError: If a prefix can't be looked up with PyOBO

    To get all the cells from MeSH:

    .. code-block:: python

        from semra.api import hydrate_subsets, filter_subsets

        configuration = {"mesh": ["mesh:D002477"], ...}
        prefix_to_identifiers = hydrate_subsets(configuration)

    It's also possible to use parents outside the vocabulary, such as when search for entity
    type in UMLS:

    .. code-block:: python

        from semra.api import hydrate_subsets, filter_subsets

        configuration = {
            "umls": [
                # all children of https://uts.nlm.nih.gov/uts/umls/semantic-network/Pathologic%20Function
                "sty:T049",  # cell or molecular dysfunction
                "sty:T047",  # disease or syndrome
                "sty:T191",  # neoplastic process
                "sty:T050",  # experimental model of disease
                "sty:T048",  # mental or behavioral dysfunction
            ],
            ...
        }
        prefix_to_identifiers = hydrate_subsets(configuration)

    """
    import pyobo
    from pyobo.getters import NoBuild

    rv: t.Dict[str, t.Set[str]] = {}
    # do lookup of the hierarchy and lookup of ancestors in 2 steps to allow for
    # querying parents inside a resource that aren't defined by it (e.g., sty terms in umls)
    for prefix, parent_curies in subset_configuration.items():
        try:
            hierarchy = pyobo.get_hierarchy(prefix, include_part_of=False, include_has_member=False)
        except NoBuild:
            rv[prefix] = set()
        except Exception as e:
            raise ValueError(f"Failed on {prefix}") from e
        else:
            rv[prefix] = {
                descendant_curie
                for parent_curie in parent_curies
                for descendant_curie in nx.ancestors(hierarchy, parent_curie) or []
            } | set(parent_curies)
    return rv


def filter_subsets(
    mappings: t.Iterable[Mapping], prefix_to_identifiers: t.Mapping[str, t.Collection[str]]
) -> t.Iterable[Mapping]:
    """Filter mappings that don't appear in the given subsets.

    :param mappings: An iterable of semantic mappings
    :param prefix_to_identifiers: A dictionary whose keys are prefixes and whose values are collections
        of local unique identifiers strings for a subset of terms in the resource to keep.

        In situations where a mapping's subject or object's prefix does not appear in this dictionary, the check
        is skipped.
    :yields: An iterable that has been filtered based on the prefix_to_identifiers dict

    If you have a simple configuration dictionary that contains the parent terms, like
    ``{"mesh": ["mesh:D002477"]}``, you'll want to do the following first:

    .. code-block:: python

        from semra.api import hydrate_subsets, filter_subsets

        mappings = [ ... ]
        configuration = {"mesh": ["mesh:D002477"]}
        prefix_to_identifiers = hydrate_subsets(configuration)
        filter_subsets(mappings, prefix_to_identifiers)
    """
    for mapping in mappings:
        if (
            mapping.s.prefix in prefix_to_identifiers
            and mapping.s.identifier not in prefix_to_identifiers[mapping.s.prefix]
        ):
            continue
        if (
            mapping.o.prefix in prefix_to_identifiers
            and mapping.o.identifier not in prefix_to_identifiers[mapping.o.prefix]
        ):
            continue
        yield mapping


def aggregate_components(
    mappings: t.Iterable[Mapping], priority: t.Collection[str]
) -> t.Mapping[t.FrozenSet[str], t.Set[t.FrozenSet[Reference]]]:
    """Get a counter where the keys are the set of all prefixes in a weakly connected component."""
    priority_set = set(priority)
    dd: t.DefaultDict[t.FrozenSet[str], t.Set[t.FrozenSet[Reference]]] = defaultdict(set)
    for component in iter_components(mappings):
        # subset to the priority prefixes
        subcomponent: t.FrozenSet[Reference] = frozenset(r for r in component if r.prefix in priority_set)
        key = frozenset(r.prefix for r in subcomponent)
        dd[key].add(subcomponent)
    return dict(dd)


def count_component_sizes(mappings: t.Iterable[Mapping], priority: t.Collection[str]) -> t.Counter[t.FrozenSet[str]]:
    """Get a counter where the keys are the set of all prefixes in a weakly connected component."""
    xx = aggregate_components(mappings, priority)
    return Counter({k: len(v) for k, v in xx.items()})


def count_coverage_sizes(mappings: t.Iterable[Mapping], priority: t.Collection[str]) -> t.Counter[int]:
    xx = count_component_sizes(mappings, priority=priority)
    counter: t.Counter[int] = Counter()
    for prefixes, count in xx.items():
        counter[len(prefixes)] += count
    # Back-fill any intermediate counts with zero
    max_key = max(counter)
    for i in range(1, max_key):
        if i not in counter:
            counter[i] = 0
    return counter
