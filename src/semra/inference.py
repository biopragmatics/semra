"""Inference functionality for SeMRA."""

from __future__ import annotations

import itertools as itt
import typing as t
from collections import Counter, defaultdict
from collections.abc import Iterable

import bioregistry
import networkx as nx
from pydantic import BaseModel
from tqdm.asyncio import tqdm

from semra.api import assemble_evidences, flip
from semra.io.graph import MULTIDIGRAPH_DATA_KEY, to_multidigraph
from semra.rules import (
    BROAD_MATCH,
    CHAIN_MAPPING,
    DB_XREF,
    EXACT_MATCH,
    FLIP,
    GENERALIZATIONS,
    KNOWLEDGE_MAPPING,
    NARROW_MATCH,
)
from semra.struct import Evidence, Mapping, ReasonedEvidence, Reference
from semra.utils import cleanup_prefixes, semra_tqdm

__all__ = [
    "infer_chains",
    "infer_dbxref_mutations",
    "infer_generalizations",
    "infer_mutations",
    "infer_mutual_dbxref_mutations",
    "infer_reversible",
]


def infer_reversible(mappings: t.Iterable[Mapping], *, progress: bool = True) -> list[Mapping]:
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
    >>> r1, r2 = get_test_reference(2)
    >>> e1 = get_test_evidence()
    >>> m1 = Mapping(subject=r1, predicate=EXACT_MATCH, object=r2, evidence=[e1])
    >>> mappings = infer_reversible([m1])
    >>> len(mappings)
    2
    >>> assert mappings[0] == m1

    .. warning::

        This operation does not "assemble", meaning if you had existing evidence
        for an inverse mapping, they will be seperate. Therefore, you can chain
        it with the :func:`assemble_evidences` operation:

        >>> from semra import Mapping, Reference, EXACT_MATCH
        >>> from semra.api import get_test_evidence
        >>> from semra.api import get_test_evidence, get_test_reference
        >>> r1, r2 = get_test_reference(2)
        >>> e1, e2 = get_test_evidence(2)
        >>> m1 = Mapping(subject=r1, predicate=EXACT_MATCH, object=r2, evidence=[e1])
        >>> m2 = Mapping(subject=r2, predicate=EXACT_MATCH, object=r1, evidence=[e2])
        >>> mappings = infer_reversible([m1, m2])
        >>> len(mappings)
        4
        >>> mappings = assemble_evidences(mappings)
        >>> len(mappings)
        2

    """
    rv = []
    for mapping in semra_tqdm(mappings, desc="Infer reverse", progress=progress):
        rv.append(mapping)
        if flipped_mapping := flip(mapping):
            rv.append(flipped_mapping)
    return rv


def infer_chains(
    mappings: list[Mapping],
    *,
    backwards: bool = True,
    progress: bool = True,
    cutoff: int = 5,
    minimum_component_size: int = 2,
    maximum_component_size: int = 100,
) -> list[Mapping]:
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
    it = tqdm(
        components, unit="component", desc="Inferring chains", unit_scale=True, disable=not progress
    )
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
            predicate_evidence_dict: defaultdict[Reference, list[Evidence]] = defaultdict(list)
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
                                subject=path_s,
                                object=path_o,
                                predicate=path_p,
                                evidence=graph[path_s][path_o][path_p][MULTIDIGRAPH_DATA_KEY],
                            )
                            for path_s, path_o, path_p in path
                        ],
                        # TODO add confidence that's inversely proportional to sg_len, i.e.
                        # larger components should return less confident mappings
                    )
                    predicate_evidence_dict[p].append(evidence)

            for p, evidences in predicate_evidence_dict.items():
                new_mappings.append(Mapping(subject=s, predicate=p, object=o, evidence=evidences))
                if backwards:
                    new_mappings.append(
                        Mapping(object=s, subject=o, predicate=FLIP[p], evidence=evidences)
                    )

    return [*mappings, *new_mappings]


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
    if predicate_set == {BROAD_MATCH} or predicate_set == {EXACT_MATCH, BROAD_MATCH}:
        return BROAD_MATCH
    if predicate_set == {NARROW_MATCH} or predicate_set == {EXACT_MATCH, NARROW_MATCH}:
        return NARROW_MATCH
    return None


def _path_has_prefix_duplicates(path: Iterable[tuple[Reference, Reference, Reference]]) -> bool:
    """Return if the path has multiple unique."""
    elements: set[Reference] = set()
    for u, v, _ in path:
        elements.add(u)
        elements.add(v)
    counter = Counter(element.prefix for element in elements)
    return any(v > 1 for v in counter.values())


def infer_mutual_dbxref_mutations(
    mappings: Iterable[Mapping],
    prefixes: Iterable[str],
    confidence: float | None = None,
    *,
    progress: bool = False,
) -> list[Mapping]:
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
    >>> r1, r2, r3 = map(Reference.from_curie, curies)
    >>> m1 = Mapping.from_triple((r1, DB_XREF, r2))
    >>> m2 = Mapping.from_triple((r2, DB_XREF, r3))
    >>> m3 = Mapping.from_triple(
    ...     (r1, EXACT_MATCH, r2),
    ...     evidence=[
    ...         ReasonedEvidence(
    ...             mappings=[m1], justification=KNOWLEDGE_MAPPING, confidence_factor=0.99
    ...         )
    ...     ],
    ... )  # this is what we are inferring
    >>> assert infer_mutual_dbxref_mutations([m1, m2], ["DOID", "mesh"], confidence=0.99) == [
    ...     m1,
    ...     m3,
    ...     m2,
    ... ]

    This function is a thin wrapper around :func:`infer_mutations` where :data:`semra.DB_XREF`
    is used as the "old" predicated and :data:`semra.EXACT_MATCH` is used as the "new" predicate.
    """
    prefixes = cleanup_prefixes(prefixes)
    pairs = {
        (subject_prefix, object_prefix)
        for subject_prefix, object_prefix in itt.product(prefixes, repeat=2)
        if subject_prefix != object_prefix
    }
    return infer_dbxref_mutations(mappings, pairs=pairs, confidence=confidence, progress=progress)


def infer_dbxref_mutations(
    mappings: Iterable[Mapping],
    pairs: dict[tuple[str, str], float] | Iterable[tuple[str, str]],
    confidence: float | None = None,
    progress: bool = False,
) -> list[Mapping]:
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
    >>> r1, r2, r3 = (Reference.from_curie(c) for c in curies)
    >>> m1 = Mapping.from_triple((r1, DB_XREF, r2))
    >>> m2 = Mapping.from_triple((r2, DB_XREF, r3))
    >>> mappings = [m1, m2]
    >>> pairs = {("DOID", "mesh"): 0.99}
    >>> m3 = Mapping.from_triple(
    ...     (r1, EXACT_MATCH, r2),
    ...     evidence=[
    ...         ReasonedEvidence(
    ...             mappings=[m1], justification=KNOWLEDGE_MAPPING, confidence_factor=0.99
    ...         )
    ...     ],
    ... )  # this is what we are inferring
    >>> assert infer_dbxref_mutations(mappings, pairs) == [m1, m3, m2]

    This function is a thin wrapper around :func:`infer_mutations` where :data:`semra.DB_XREF`
    is used as the "old" predicated and :data:`semra.EXACT_MATCH` is used as the "new" predicate.
    """
    if confidence is None:
        confidence = 0.7
    if not isinstance(pairs, dict):
        pairs = dict.fromkeys(pairs, confidence)
    return infer_mutations(
        mappings,
        pairs=pairs,
        old_predicate=DB_XREF,
        new_predicate=EXACT_MATCH,
        progress=progress,
    )


def infer_mutations(
    mappings: Iterable[Mapping],
    pairs: dict[tuple[str, str], float],
    old_predicate: Reference,
    new_predicate: Reference,
    *,
    progress: bool = False,
) -> list[Mapping]:
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
    >>> from semra.rules import KNOWLEDGE_MAPPING
    >>> curies = "DOID:0050577", "mesh:C562966", "umls:C4551571"
    >>> r1, r2, r3 = (Reference.from_curie(c) for c in curies)
    >>> m1 = Mapping.from_triple((r1, DB_XREF, r2))
    >>> m2 = Mapping.from_triple((r2, DB_XREF, r3))
    >>> pairs = {("DOID", "mesh"): 0.99}
    >>> m3 = Mapping.from_triple(
    ...     (r1, EXACT_MATCH, r2),
    ...     evidence=[
    ...         ReasonedEvidence(
    ...             mappings=[m1], justification=KNOWLEDGE_MAPPING, confidence_factor=0.99
    ...         )
    ...     ],
    ... )  # this is what we are inferring  # this is what we are inferring
    >>> mappings = infer_mutations([m1, m2], pairs, DB_XREF, EXACT_MATCH)
    >>> assert mappings == [m1, m3, m2]
    """
    configurations = [
        Configuration(
            old=old_predicate,
            new=new_predicate,
            pairs=_clean_pairs(pairs),
        )
    ]
    return _mutate(mappings, configurations, progress=progress)


class Configuration(BaseModel):
    """A configuration for mutation."""

    old: Reference
    new: Reference
    default_confidence: float | None = None
    pairs: dict[tuple[str, str], float] | None = None


def _mutate(
    mappings: Iterable[Mapping],
    configurations: list[Configuration],
    *,
    progress: bool = False,
) -> list[Mapping]:
    rv = []

    # index all configurations
    upgrade_map = {c.old: c for c in configurations}

    for mapping in semra_tqdm(mappings, desc="Adding mutated predicates", progress=progress):
        rv.append(mapping)
        configuration = upgrade_map.get(mapping.predicate)
        if configuration is None:
            continue

        confidence_factor: float | None
        if configuration.default_confidence:
            confidence_factor = configuration.default_confidence
        elif configuration.pairs:
            confidence_factor = configuration.pairs.get(
                (mapping.subject.prefix, mapping.object.prefix)
            )
        else:
            raise ValueError

        if confidence_factor is None:
            # This means that there was no explicit confidence set for the
            # subject/object prefix pair, meaning it wasn't asked to be inferred
            continue
        inferred_mapping = Mapping(
            subject=mapping.subject,
            predicate=configuration.new,
            object=mapping.object,
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


def _clean_pairs(pairs: dict[tuple[str, str], float]) -> dict[tuple[str, str], float]:
    rv = {}
    for (p1, p2), v in pairs.items():
        p1_norm = bioregistry.normalize_prefix(p1, strict=True)
        p2_norm = bioregistry.normalize_prefix(p2, strict=True)
        rv[p1_norm, p2_norm] = v
    return rv


def infer_generalizations(
    mappings: list[Mapping],
    *,
    progress: bool = False,
) -> list[Mapping]:
    """Apply generalization rules.

    :param mappings: Mappings to process
    :param progress: Should a progress bar be used?
    :returns:
        Mappings that have been mutated to relax relations configured
        by :data:`semra.rules.GENERALIZATIONS`

    .. seealso:: Rules definition in SSSOM https://mapping-commons.github.io/sssom/chaining-rules/#generalisation-rules
    """
    configurations = [
        Configuration(old=old, new=new, default_confidence=1.0)
        for old, new in GENERALIZATIONS.items()
    ]
    return _mutate(mappings, configurations, progress=progress)
