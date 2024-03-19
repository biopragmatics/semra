"""Semantic Mapping Reasoning Assembler."""

from __future__ import annotations

import itertools as itt
import logging
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

logger = logging.getLogger(__name__)

PREDICATE_KEY = "predicate"
EVIDENCE_KEY = "evidence"

#: An index allows for the aggregation of evidences for each core triple
Index = t.Dict[Triple, t.List[Evidence]]


def _tqdm(mappings, desc: str | None = None, *, progress: bool = True):
    return tqdm(
        mappings,
        unit_scale=True,
        unit="mapping",
        desc=desc,
        disable=not progress,
    )


TEST_MAPPING_SET = MappingSet(name="Test Mapping Set", confidence=0.95)


def get_test_evidence(n: t.Optional[int] = None) -> t.Union[SimpleEvidence, t.List[SimpleEvidence]]:
    """Get test evidence."""
    if n is None:
        return SimpleEvidence(mapping_set=TEST_MAPPING_SET)
    return [SimpleEvidence(mapping_set=TEST_MAPPING_SET) for _ in range(n)]


def get_test_reference(n: t.Optional[int] = None, prefix: str = "test") -> t.List[Reference]:
    """Get test reference(s)."""
    if n is None:
        Reference(prefix=prefix, identifier="1")
    return [Reference(prefix=prefix, identifier=str(i + 1)) for i in range(n)]


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


def get_index(mappings: Iterable[Mapping], *, progress: bool = True) -> Index:
    """Aggregate and deduplicate evidences for each core triple."""
    dd: t.DefaultDict[Triple, t.List[Evidence]] = defaultdict(list)
    for mapping in _tqdm(mappings, desc="Indexing mappings", progress=progress):
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
    """Extend the mapping list with flipped mappings

    :param mappings: An iterable of mappings
    :param progress: Should a progress bar be shown? Defaults to true.
    :returns:
        A list where if a mapping can be flipped (i.e., :func:`flip`), a flipped
        mapping is added. Flipped mappings contain reasoned evidence
        :class:`ReasonedEvidence` objects that point to the mapping from which
        the evidence was derived.

    >>> from semra import Mapping, Reference, EXACT_MATCH, SimpleEvidence
    >>> from semra.api import get_test_evidence, get_test_reference
    >>> r1 = get_test_reference(prefix="p1")
    >>> r2 = get_test_reference(prefix="p2")
    >>> e1 = get_test_evidence()
    >>> m1 = Mapping(s=r1, p=EXACT_MATCH, o=r2, evidence=[e1])
    >>> mappings = infer_reversible([m1])
    >>> len(mappings)
    2
    >>> mappings[0] == m1
    >>> mappings[1] ==

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
        >>> mappings = infer_reversible([m1, m2])
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


def to_digraph(mappings: t.List[Mapping]) -> nx.DiGraph:
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
            **{PREDICATE_KEY: mapping.p, EVIDENCE_KEY: mapping.evidence},
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
    mappings: t.List[Mapping], *, backwards: bool = True, progress: bool = True, cutoff: int = 5
) -> t.List[Mapping]:
    """Apply graph-based reasoning over mapping chains to infer new mappings.

    :param mappings: A list of input mappings
    :param backwards: Should inference be done in reverse?
    :param progress: Should a progress bar be shown? Defaults to true.
    :param cutoff: What's the maximum length path to infer over?
    :return: The list of input mappings _plus_ inferred mappings
    """
    mappings = assemble_evidences(mappings, progress=progress)
    # FIXME to_digraph requires a single predicate for each s/o pair,
    #  which isn't necessarily true, so there should be some kind of reasoning
    #  step that picks which is "best"
    graph = to_digraph(mappings)
    new_mappings = []

    components = sorted(
        (c for c in nx.weakly_connected_components(graph) if len(c) > 2),  # noqa: PLR2004
        key=len,
        reverse=True,
    )
    it = tqdm(components, unit="component", desc="Inferring chains", unit_scale=True, disable=not progress)
    for _i, component in enumerate(it):
        sg: nx.DiGraph = graph.subgraph(component).copy()
        it.set_postfix(size=sg.number_of_nodes())
        for s, o in itt.combinations(sg, 2):
            if sg.has_edge(s, o):  # do not overwrite existing mappings
                continue
            # TODO there has to be a way to reimplement transitive closure to handle this
            # nx.shortest_path(sg, s, o)
            for path in nx.all_simple_edge_paths(sg, s, o, cutoff=cutoff):
                predicates = [sg[u][v][PREDICATE_KEY] for u, v in path]
                p = _reason_multiple_predicates(predicates)
                if p:
                    evidence = ReasonedEvidence(
                        justification=CHAIN_MAPPING,
                        mappings=[
                            Mapping(
                                s=path_s,
                                o=path_o,
                                p=graph[path_s][path_o][PREDICATE_KEY],
                                evidence=graph[path_s][path_o][EVIDENCE_KEY],
                            )
                            for path_s, path_o in path
                        ],
                    )
                    new_mappings.append(Mapping(s=s, p=p, o=o, evidence=[evidence]))
                    if backwards:
                        new_mappings.append(Mapping(o=s, s=o, p=FLIP[p], evidence=[evidence]))
    return [*mappings, *new_mappings]


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

    def key(pair):
        return triple_key(pair[0])

    for (s, p, o), evidences in sorted(index.items(), key=key):
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
) -> t.List[Mapping]:
    pairs = {(s, t) for s, t in itt.product(prefixes, repeat=2) if s != t}
    return infer_dbxref_mutations(mappings, pairs=pairs, confidence=confidence)


def infer_dbxref_mutations(
    mappings: Iterable[Mapping],
    pairs: t.Dict[t.Tuple[str, str], float] | Iterable[t.Tuple[str, str]],
    confidence: float | None = None,
) -> t.List[Mapping]:
    """Upgrade database cross-references into exact matches for the given pairs.

    :param mappings: A list of mappings
    :param pairs: A dictionary of source/target prefix pairs to the confidence of upgrading dbxrefs.
        If giving a collection of pairs, will assume a default confidence of 0.7.
    :return: A new list of mappings containing upgrades
    """
    if confidence is None:
        confidence = 0.7
    if not isinstance(pairs, dict):
        pairs = {pair: confidence for pair in pairs}
    return infer_mutations(
        mappings,
        pairs=pairs,
        old=DB_XREF,
        new=EXACT_MATCH,
    )


def infer_mutations(
    mappings: Iterable[Mapping],
    pairs: t.Dict[t.Tuple[str, str], float],
    old: Reference,
    new: Reference,
    *,
    progress: bool = False,
) -> t.List[Mapping]:
    """Infer mappings with alternate predicates for the given prefix pairs.

    :param mappings: Mappings to infer from
    :param pairs: A dictionary of pairs of (subject prefix, object prefix) to the confidence
        of inference
    :param old: The predicate on which inference should be done
    :param new: The predicate to get inferred
    :returns: A list of all old mapping plus inferred ones interspersed.
    """
    rv = []
    for mapping in _tqdm(mappings, desc="Adding mutated predicates", progress=progress):
        rv.append(mapping)
        confidence = pairs.get((mapping.s.prefix, mapping.o.prefix))
        if confidence is None or mapping.p != old:
            continue
        inferred_mapping = Mapping(
            s=mapping.s,
            p=new,
            o=mapping.o,
            evidence=[
                ReasonedEvidence(
                    justification=KNOWLEDGE_MAPPING,
                    mappings=[mapping],
                    confidence_factor=confidence,
                )
            ],
        )
        rv.append(inferred_mapping)
    return rv


def keep_prefixes(
    mappings: Iterable[Mapping], prefixes: str | Iterable[str], *, progress: bool = True
) -> t.List[Mapping]:
    """Filter out mappings whose subject or object are not in the given list of prefixes."""
    prefixes = {prefixes} if isinstance(prefixes, str) else set(prefixes)
    return [
        mapping
        for mapping in _tqdm(mappings, desc=f"Keeping from {len(prefixes)} prefixes", progress=progress)
        if mapping.s.prefix in prefixes and mapping.o.prefix in prefixes
    ]


def keep_subject_prefixes(mappings: Iterable[Mapping], prefixes: str | Iterable[str], *, progress: bool = True):
    prefixes = {prefixes} if isinstance(prefixes, str) else set(prefixes)
    return [
        mapping
        for mapping in _tqdm(mappings, desc="Filtering subject prefixes", progress=progress)
        if mapping.s.prefix in prefixes
    ]


def keep_object_prefixes(mappings: Iterable[Mapping], prefixes: str | Iterable[str], *, progress: bool = True):
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

    This algorithm works in the following way:

    1. Get the subset of exact matches from the input mapping list
    2. Convert the exact matches to an undirected mapping graph
    3. Extract connected components
    4. For each component:
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
