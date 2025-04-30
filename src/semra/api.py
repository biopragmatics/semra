"""Semantic Mapping Reasoning Assembler."""

from __future__ import annotations

import itertools as itt
import logging
import typing
import typing as t
from collections import Counter, defaultdict
from collections.abc import Iterable
from typing import Literal, TypeVar, cast, overload

import bioregistry
import networkx as nx
import pandas as pd
import ssslm
from ssslm import LiteralMapping
from tqdm.auto import tqdm

from semra.io.graph import _from_digraph_edge, to_digraph
from semra.rules import EXACT_MATCH, FLIP, INVERSION_MAPPING, SubsetConfiguration
from semra.struct import (
    Evidence,
    Mapping,
    MappingSet,
    ReasonedEvidence,
    Reference,
    SimpleEvidence,
    Triple,
)
from semra.utils import cleanup_prefixes, semra_tqdm

__all__ = [
    "TEST_MAPPING_SET",
    "Index",
    "M2MIndex",
    "assemble_evidences",
    "assert_projection",
    "count_component_sizes",
    "count_source_target",
    "deduplicate_evidence",
    "filter_many_to_many",
    "filter_mappings",
    "filter_minimum_confidence",
    "filter_prefixes",
    "filter_self_matches",
    "filter_subsets",
    "flip",
    "get_index",
    "get_many_to_many",
    "get_priority_reference",
    "get_test_evidence",
    "get_test_reference",
    "hydrate_subsets",
    "keep_object_prefixes",
    "keep_prefixes",
    "keep_subject_prefixes",
    "print_source_target_counts",
    "prioritize",
    "prioritize_df",
    "project",
    "project_dict",
    "str_source_target_counts",
    "summarize_prefixes",
    "tabulate_index",
    "unindex",
    "update_literal_mappings",
    "validate_mappings",
]

logger = logging.getLogger(__name__)

#: An index allows for the aggregation of evidences for each core triple
Index = dict[Triple, list[Evidence]]

X = TypeVar("X")

#: A test mapping set that can be used in examples.
TEST_MAPPING_SET = MappingSet(name="Test Mapping Set", confidence=0.95)


# docstr-coverage: inherited
@typing.overload
def get_test_evidence(n: int) -> list[SimpleEvidence]: ...


# docstr-coverage: inherited
@typing.overload
def get_test_evidence(n: None) -> SimpleEvidence: ...


def get_test_evidence(n: int | None = None) -> SimpleEvidence | list[SimpleEvidence]:
    """Get test evidence."""
    if isinstance(n, int):
        return [
            SimpleEvidence(
                mapping_set=TEST_MAPPING_SET,
                author=Reference(prefix="orcid", identifier=f"0000-0000-0000-000{n}"),
            )
            for n in range(n)
        ]
    return SimpleEvidence(mapping_set=TEST_MAPPING_SET)


# docstr-coverage: inherited
@typing.overload
def get_test_reference(n: int, prefix: str) -> list[Reference]: ...


# docstr-coverage: inherited
@typing.overload
def get_test_reference(n: None, prefix: str) -> Reference: ...


def get_test_reference(n: int | None = None, prefix: str = "go") -> Reference | list[Reference]:
    """Get test reference(s)."""
    if isinstance(n, int):
        return [Reference(prefix=prefix, identifier=str(i + 1).zfill(7)) for i in range(n)]
    return Reference(prefix=prefix, identifier="0000001")


def count_source_target(mappings: Iterable[Mapping]) -> Counter[tuple[str, str]]:
    """Count pairs of source/target prefixes.

    :param mappings: An iterable of mappings
    :return:
        A counter whose keys are pairs of source prefixes and target prefixes
        appearing in the mappings

    >>> from semra import Mapping, Reference, EXACT_MATCH
    >>> from semra.api import get_test_reference
    >>> r1, r2 = get_test_reference(2)
    >>> m1 = Mapping(subject=r1, predicate=EXACT_MATCH, object=r2)
    >>> counter = count_source_target([m1])
    """
    return Counter((triple.subject.prefix, triple.object.prefix) for triple in get_index(mappings))


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
    dd: defaultdict[Triple, list[Evidence]] = defaultdict(list)
    for mapping in semra_tqdm(mappings, desc="Indexing mappings", progress=progress, leave=leave):
        dd[mapping.triple].extend(mapping.evidence)
    return {triple: deduplicate_evidence(triple, evidence) for triple, evidence in dd.items()}


def assemble_evidences(mappings: list[Mapping], *, progress: bool = True) -> list[Mapping]:
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
    >>> r1, r2 = get_test_reference(2)
    >>> e1, e2 = get_test_evidence(2)
    >>> m1 = Mapping(subject=r1, predicate=EXACT_MATCH, object=r2, evidence=[e1])
    >>> m2 = Mapping(subject=r1, predicate=EXACT_MATCH, object=r2, evidence=[e2])
    >>> m = assemble_evidences([m1, m2])
    >>> assert m == [Mapping(subject=r1, predicate=EXACT_MATCH, object=r2, evidence=[e1, e2])]
    """
    index = get_index(mappings, progress=progress)
    return unindex(index, progress=progress)


# TODO infer negative mappings for exact match from narrow/broad match


# docstr-coverage:excused `overload`
@overload
def flip(mapping: Mapping, *, strict: Literal[True] = True) -> Mapping: ...


# docstr-coverage:excused `overload`
@overload
def flip(mapping: Mapping, *, strict: Literal[False] = False) -> Mapping | None: ...


def flip(mapping: Mapping, *, strict: bool = False) -> Mapping | None:
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
    if (p := FLIP.get(mapping.predicate)) is not None:
        return Mapping(
            subject=mapping.object,
            predicate=p,
            object=mapping.subject,
            evidence=[ReasonedEvidence(justification=INVERSION_MAPPING, mappings=[mapping])],
        )
    elif strict:
        raise ValueError
    else:
        return None


def iter_components(mappings: t.Iterable[Mapping]) -> t.Iterable[set[Reference]]:
    """Iterate over connected components in the multidigraph view over the mappings."""
    graph = to_digraph(mappings)
    return cast(t.Iterable[set[Reference]], nx.weakly_connected_components(graph))


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

    rows: list[tuple[str, str, str, str]] = []
    for triple, evidences in sorted(index.items()):
        if not evidences:
            rows.append((triple.subject.curie, triple.predicate.curie, triple.object.curie, ""))
        else:
            first, *rest = evidences
            rows.append(
                (triple.subject.curie, triple.predicate.curie, triple.object.curie, str(first))
            )
            for r in rest:
                rows.append(("", "", "", str(r)))
    return tabulate(rows, headers=["s", "p", "o", "ev"], tablefmt="github")


def keep_prefixes(
    mappings: Iterable[Mapping], prefixes: str | Iterable[str], *, progress: bool = True
) -> list[Mapping]:
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
    prefixes = cleanup_prefixes(prefixes)
    return [
        mapping
        for mapping in semra_tqdm(
            mappings, desc=f"Keeping from {len(prefixes)} prefixes", progress=progress
        )
        if mapping.subject.prefix in prefixes and mapping.object.prefix in prefixes
    ]


def keep_subject_prefixes(
    mappings: Iterable[Mapping], prefixes: str | Iterable[str], *, progress: bool = True
) -> list[Mapping]:
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
    >>> assert keep_subject_prefixes([m1, m2, m3], {"DOID"})
    """
    prefixes = cleanup_prefixes(prefixes)
    return [
        mapping
        for mapping in semra_tqdm(mappings, desc="Filtering subject prefixes", progress=progress)
        if mapping.subject.prefix in prefixes
    ]


def keep_object_prefixes(
    mappings: Iterable[Mapping], prefixes: str | Iterable[str], *, progress: bool = True
) -> list[Mapping]:
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
    >>> assert keep_object_prefixes([m1, m2, m3], {"mesh"}) == [m1]
    """
    prefixes = cleanup_prefixes(prefixes)
    return [
        mapping
        for mapping in semra_tqdm(mappings, desc="Filtering object prefixes", progress=progress)
        if mapping.object.prefix in prefixes
    ]


def filter_prefixes(
    mappings: Iterable[Mapping], prefixes: str | Iterable[str], *, progress: bool = True
) -> list[Mapping]:
    """Filter out mappings whose subject or object are in the given list of prefixes."""
    prefixes = cleanup_prefixes(prefixes)
    return [
        mapping
        for mapping in semra_tqdm(
            mappings, desc=f"Filtering out {len(prefixes)} prefixes", progress=progress
        )
        if mapping.subject.prefix not in prefixes and mapping.object.prefix not in prefixes
    ]


def filter_self_matches(mappings: Iterable[Mapping], *, progress: bool = True) -> list[Mapping]:
    """Filter out mappings within the same resource."""
    return [
        mapping
        for mapping in semra_tqdm(mappings, desc="Filtering out self-matches", progress=progress)
        if mapping.subject.prefix != mapping.object.prefix
    ]


def filter_mappings(
    mappings: list[Mapping], skip_mappings: list[Mapping], *, progress: bool = True
) -> list[Mapping]:
    """Filter out mappings in the second set from the first set."""
    skip_triples = {skip_mapping.triple for skip_mapping in skip_mappings}
    return [
        mapping
        for mapping in semra_tqdm(mappings, desc="Filtering mappings", progress=progress)
        if mapping.triple not in skip_triples
    ]


#: A multi-leveled nested dictionary that represents many-to-many mappings.
#: The first key is subject/object pairs, the second key is either a subject identifier or object identifier,
#: the last key is the opposite object or subject identifier, and the values are a list of mappings.
#:
#: This data structure can be used to index either forward or backwards mappings,
#: as done inside :func:`get_many_to_many`
M2MIndex = defaultdict[tuple[str, str], defaultdict[str, defaultdict[str, list[Mapping]]]]


def get_many_to_many(mappings: list[Mapping]) -> list[Mapping]:
    """Get many-to-many mappings, disregarding predicate type."""
    forward: M2MIndex = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    backward: M2MIndex = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    for mapping in mappings:
        forward[mapping.subject.prefix, mapping.object.prefix][mapping.subject.identifier][
            mapping.object.identifier
        ].append(mapping)
        backward[mapping.subject.prefix, mapping.object.prefix][mapping.object.identifier][
            mapping.subject.identifier
        ].append(mapping)

    index: defaultdict[Triple, list[Evidence]] = defaultdict(list)
    for preindex in [forward, backward]:
        for d1 in preindex.values():
            for d2 in d1.values():
                if len(d2) > 1:  # means there are multiple identifiers mapped
                    for mapping in itt.chain.from_iterable(d2.values()):
                        index[mapping.triple].extend(mapping.evidence)

    # this is effectively the same as :func:`unindex` except the deduplicate_evidence is called
    # explicitly
    rv = [
        Mapping.from_triple(triple, deduplicate_evidence(triple, evidence))
        for triple, evidence in index.items()
    ]
    return rv


def filter_many_to_many(mappings: list[Mapping], *, progress: bool = True) -> list[Mapping]:
    """Filter out many to many mappings."""
    skip_mappings = get_many_to_many(mappings)
    return filter_mappings(mappings, skip_mappings, progress=progress)


# docstr-coverage:excused `overload`
@overload
def project(
    mappings: Iterable[Mapping],
    source_prefix: str,
    target_prefix: str,
    *,
    return_sus: typing.Literal[True] = ...,
    progress: bool = False,
) -> tuple[list[Mapping], list[Mapping]]: ...


# docstr-coverage:excused `overload`
@overload
def project(
    mappings: Iterable[Mapping],
    source_prefix: str,
    target_prefix: str,
    *,
    return_sus: typing.Literal[False] = ...,
    progress: bool = False,
) -> list[Mapping]: ...


def project(
    mappings: Iterable[Mapping],
    source_prefix: str,
    target_prefix: str,
    *,
    return_sus: bool = False,
    progress: bool = False,
) -> list[Mapping] | tuple[list[Mapping], list[Mapping]]:
    """Ensure that each identifier only appears as the subject of one mapping."""
    mappings = keep_subject_prefixes(mappings, source_prefix, progress=progress)
    mappings = keep_object_prefixes(mappings, target_prefix, progress=progress)
    mappings_list = list(mappings)
    m2m_mappings = get_many_to_many(mappings_list)
    mappings_list = filter_mappings(mappings_list, m2m_mappings, progress=progress)
    mappings_list = assemble_evidences(mappings_list, progress=progress)
    if return_sus:
        return mappings_list, m2m_mappings
    return mappings_list


def project_dict(mappings: list[Mapping], source_prefix: str, target_prefix: str) -> dict[str, str]:
    """Get a dictionary from source identifiers to target identifiers."""
    mappings = cast(list[Mapping], project(mappings, source_prefix, target_prefix))
    return {mapping.subject.identifier: mapping.object.identifier for mapping in mappings}


def assert_projection(mappings: list[Mapping]) -> None:
    """Raise an exception if any entities appear as the subject in multiple mappings."""
    counter = Counter(m.subject for m in mappings)
    counter = Counter({k: v for k, v in counter.items() if v > 1})
    if not counter:
        return
    raise ValueError(
        f"Some subjects appear in multiple mappings, therefore this is not a "
        f"valid projection. Showing top 5: {counter.most_common(20)}"
    )


def prioritize(mappings: list[Mapping], priority: list[str]) -> list[Mapping]:
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
    mappings = [m for m in mappings if m.predicate == EXACT_MATCH]
    exact_mappings = len(mappings)
    priority = _clean_priority_prefixes(priority)

    graph = to_digraph(mappings).to_undirected()
    rv: list[Mapping] = []
    for component in tqdm(nx.connected_components(graph), unit="component", unit_scale=True):
        o = get_priority_reference(component, priority)
        if o is None:
            continue
        rv.extend(
            mapping
            # TODO should this work even if s-o edge not exists?
            #  can also do "inference" here, but also might be
            #  because of negative edge filtering
            for s in component
            if s != o and graph.has_edge(s, o)
            for mapping in _from_digraph_edge(graph, s, o)
        )

    # sort such that the mappings are ordered by object by priority order
    # then identifier of object, then subject prefix in alphabetical order
    pos = {prefix: i for i, prefix in enumerate(priority)}
    rv = sorted(
        rv,
        key=lambda m: (
            pos[m.object.prefix],
            m.object.identifier,
            m.subject.prefix,
            m.subject.identifier,
        ),
    )

    end_mappings = len(rv)
    logger.info(
        f"Prioritized from {original_mappings:,} original ({exact_mappings:,} exact) to {end_mappings:,}"
    )
    return rv


def _clean_priority_prefixes(priority: list[str]) -> list[str]:
    return [bioregistry.normalize_prefix(prefix, strict=True) for prefix in priority]


def get_priority_reference(
    component: t.Iterable[Reference], priority: list[str]
) -> Reference | None:
    """Get the priority reference from a component.

    :param component: A set of references with the pre-condition that they're all "equivalent"
    :param priority: A priority list of prefixes, where earlier in the list means the priority is higher
    :returns:
        Returns the reference with the prefix that has the highest priority.
        If multiple references have the highest priority prefix, returns the first one encountered.
        If none have a priority prefix, return None.

    >>> from semra import Reference
    >>> curies = ["DOID:0050577", "mesh:C562966", "umls:C4551571"]
    >>> references = [Reference.from_curie(curie) for curie in curies]
    >>> get_priority_reference(references, ["mesh", "umls"]).curie
    'mesh:C562966'
    >>> get_priority_reference(references, ["DOID", "mesh", "umls"]).curie
    'doid:0050577'
    >>> get_priority_reference(references, ["hpo", "ordo", "symp"])

    """
    prefix_to_references: defaultdict[str, list[Reference]] = defaultdict(list)
    for reference in component:
        prefix_to_references[reference.prefix].append(reference)
    for prefix in _clean_priority_prefixes(priority):
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


def unindex(index: Index, *, progress: bool = True) -> list[Mapping]:
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
    >>> assert unindex(index) == [Mapping(subject=s, predicate=p, object=o, evidence=[e1])]
    """
    return [
        Mapping.from_triple(triple, evidence=evidence)
        for triple, evidence in semra_tqdm(
            index.items(), desc="Unindexing mappings", progress=progress
        )
    ]


def deduplicate_evidence(triple: Triple | Mapping, evidence: list[Evidence]) -> list[Evidence]:
    """Deduplicate a list of evidences based on their "key" function."""
    d = {e.key(triple): e for e in evidence}
    return list(d.values())


def validate_mappings(mappings: list[Mapping], *, progress: bool = True) -> None:
    """Validate mappings against the Bioregistry and raise an error on the first invalid."""
    import bioregistry

    for mapping in tqdm(
        mappings, desc="Validating mappings", unit_scale=True, unit="mapping", disable=not progress
    ):
        if bioregistry.normalize_prefix(mapping.subject.prefix) != mapping.subject.prefix:
            raise ValueError(
                f"invalid subject prefix.\n\nMapping: {mapping}\n\nSubject:{mapping.subject}."
            )
        if bioregistry.normalize_prefix(mapping.object.prefix) != mapping.object.prefix:
            raise ValueError(f"invalid object prefix: {mapping}.")
        if not bioregistry.is_valid_identifier(mapping.subject.prefix, mapping.subject.identifier):
            raise ValueError(
                f"Invalid mapping subject."
                f"\n\nMapping:{mapping}."
                f"\n\nSubject: {mapping.subject}"
                f"\n\nUse regex {bioregistry.get_pattern(mapping.subject.prefix)}"
            )
        if ":" in mapping.subject.identifier:
            raise ValueError(f"banana in mapping subject: {mapping}")
        if not bioregistry.is_valid_identifier(mapping.object.prefix, mapping.object.identifier):
            raise ValueError(
                f"Invalid mapping object."
                f"\n\nMapping:{mapping}."
                f"\n\nObject: {mapping.object}"
                f"\n\nUse regex {bioregistry.get_pattern(mapping.object.prefix)}"
            )
        if ":" in mapping.object.identifier:
            raise ValueError(f"banana in mapping object: {mapping}")


def summarize_prefixes(mappings: list[Mapping]) -> pd.DataFrame:
    """Get a dataframe summarizing the prefixes appearing in the mappings."""
    import bioregistry

    prefixes = set(itt.chain.from_iterable((m.object.prefix, m.subject.prefix) for m in mappings))
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


def filter_minimum_confidence(
    mappings: Iterable[Mapping], cutoff: float = 0.7
) -> Iterable[Mapping]:
    """Filter mappings below a given confidence."""
    for mapping in mappings:
        try:
            confidence = mapping.get_confidence()
        except ValueError:
            continue
        if confidence >= cutoff:
            yield mapping


def hydrate_subsets(
    subset_configuration: SubsetConfiguration,
    *,
    show_progress: bool = True,
) -> SubsetConfiguration:
    """Convert a subset configuration dictionary into a subset artifact.

    :param subset_configuration: A dictionary of prefixes to sets of parent terms
    :param show_progress: Should progress bars be shown?
    :return: A dictionary that uses the is-a hierarchy within the resources to get full term lists
    :raises ValueError: If a prefix can't be looked up with PyOBO

    To get all the cells from MeSH:

    .. code-block:: python

        from semra.api import hydrate_subsets, filter_subsets

        configuration = {"mesh": ["mesh:D002477"], ...}
        prefix_to_references = hydrate_subsets(configuration)

    It's also possible to use parents outside the vocabulary, such as when search for entity
    type in UMLS:

    .. code-block:: python

        from semra import Reference
        from semra.api import hydrate_subsets, filter_subsets

        configuration = {
            "umls": [
                # all children of https://uts.nlm.nih.gov/uts/umls/semantic-network/Pathologic%20Function
                Reference.from_curie("sty:T049"),  # cell or molecular dysfunction
                Reference.from_curie("sty:T047"),  # disease or syndrome
                Reference.from_curie("sty:T191"),  # neoplastic process
                Reference.from_curie("sty:T050"),  # experimental model of disease
                Reference.from_curie("sty:T048"),  # mental or behavioral dysfunction
            ],
            ...
        }
        prefix_to_references = hydrate_subsets(configuration)

    """
    import pyobo

    rv: dict[str, set[Reference]] = {}
    # do lookup of the hierarchy and lookup of ancestors in 2 steps to allow for
    # querying parents inside a resource that aren't defined by it (e.g., sty terms in umls)
    for prefix, parents in subset_configuration.items():
        try:
            hierarchy = pyobo.get_hierarchy(
                prefix, include_part_of=False, include_has_member=False, use_tqdm=show_progress
            )
        except RuntimeError:  # e.g., no build
            rv[prefix] = set()
        except Exception as e:
            raise ValueError(f"Failed on {prefix}") from e
        else:
            rv[prefix] = {
                descendant
                for parent in parents
                for descendant in nx.ancestors(hierarchy, parent) or []
                if descendant.prefix == prefix
            }
            for parent in parents:
                if parent.prefix == prefix:
                    rv[prefix].add(parent)
    return {k: sorted(v) for k, v in rv.items()}


def filter_subsets(
    mappings: t.Iterable[Mapping], prefix_to_references: SubsetConfiguration
) -> list[Mapping]:
    """Filter mappings that don't appear in the given subsets.

    :param mappings: An iterable of semantic mappings
    :param prefix_to_references: A dictionary whose keys are prefixes and whose values are collections
        of references for a subset of terms in the resource to keep.

        In situations where a mapping's subject or object's prefix does not appear in this dictionary, the check
        is skipped.
    :return: A list that has been filtered based on the prefix_to_identifiers dict
    :raises ValueError: If CURIEs are given instead of identifiers

    If you have a simple configuration dictionary that contains the parent terms, like
    ``{"mesh": [Reference.from_curie("mesh:D002477")]}``, you'll want to do the following first:

    .. code-block:: python

        from semra import Reference
        from semra.api import hydrate_subsets, filter_subsets

        mappings = [...]
        configuration = {"mesh": [Reference.from_curie("mesh:D002477")]}
        prefix_to_identifiers = hydrate_subsets(configuration)
        filter_subsets(mappings, prefix_to_identifiers)
    """
    clean_prefix_to_identifiers = _clean_subset_configuration(prefix_to_references)
    rv = []
    for mapping in mappings:
        if (
            mapping.subject.prefix in clean_prefix_to_identifiers
            and mapping.subject not in clean_prefix_to_identifiers[mapping.subject.prefix]
        ):
            continue
        if (
            mapping.object.prefix in clean_prefix_to_identifiers
            and mapping.object not in clean_prefix_to_identifiers[mapping.object.prefix]
        ):
            continue
        rv.append(mapping)
    return rv


def _clean_subset_configuration(
    prefix_to_references: SubsetConfiguration,
) -> dict[str, set[Reference]]:
    clean_prefix_to_identifiers = {}
    for prefix, references in prefix_to_references.items():
        if not references:  # skip empty lists
            continue
        norm_prefix = bioregistry.normalize_prefix(prefix, strict=True)
        clean_prefix_to_identifiers[norm_prefix] = set(references)
    return clean_prefix_to_identifiers


def aggregate_components(
    mappings: t.Iterable[Mapping],
    prefix_allowlist: str | t.Collection[str] | None = None,
) -> t.Mapping[frozenset[str], set[frozenset[Reference]]]:
    """Get a counter where the keys are the set of all prefixes in a weakly connected component.

    :param mappings: Mappings to aggregate
    :param prefix_allowlist: An optional prefix filter - only keeps prefixes in this list
    :returns: A dictionary mapping from a frozenset of prefixes to a set of frozensets of references
    """
    dd: defaultdict[frozenset[str], set[frozenset[Reference]]] = defaultdict(set)
    components = iter_components(mappings)

    if prefix_allowlist is not None:
        prefix_set = cleanup_prefixes(prefix_allowlist)
        for component in components:
            # subset to the priority prefixes
            subcomponent: frozenset[Reference] = frozenset(
                r for r in component if r.prefix in prefix_set
            )
            key = frozenset(r.prefix for r in subcomponent)
            dd[key].add(subcomponent)
    else:
        for component in components:
            subcomponent = frozenset(component)
            key = frozenset(r.prefix for r in subcomponent)
            dd[key].add(subcomponent)

    return dict(dd)


def count_component_sizes(
    mappings: t.Iterable[Mapping], prefix_allowlist: str | t.Collection[str] | None = None
) -> t.Counter[frozenset[str]]:
    """Get a counter where the keys are the set of all prefixes in a weakly connected component."""
    xx = aggregate_components(mappings, prefix_allowlist)
    return Counter({k: len(v) for k, v in xx.items()})


def count_coverage_sizes(
    mappings: t.Iterable[Mapping], prefix_allowlist: str | t.Collection[str] | None = None
) -> t.Counter[int]:
    """Get a counter of the number of prefixes in which each entity appears based on the mappings."""
    xx = count_component_sizes(mappings, prefix_allowlist=prefix_allowlist)
    counter: t.Counter[int] = Counter()
    for prefixes, count in xx.items():
        counter[len(prefixes)] += count
    # Back-fill any intermediate counts with zero
    max_key = max(counter)
    for i in range(1, max_key):
        if i not in counter:
            counter[i] = 0
    return counter


def update_literal_mappings(
    literal_mappings: list[LiteralMapping], mappings: list[Mapping]
) -> list[LiteralMapping]:
    """Use a priority mapping to re-write terms with priority groundings.

    :param literal_mappings: A list of literal mappings
    :param mappings: A list of SeMRA mapping objects, constituting a priority mapping.
        This means that each mapping has a unique subject.
    :return: A new list of literal mappings that have been remapped

    .. code-block:: python

        from itertools import chain

        from pyobo import get_literal_mappings
        from ssslm.ner import make_grounder

        from semra import Configuration, Input
        from semra.api import update_literal_mappings

        prefixes = ["doid", "mondo", "efo"]

        # 1. Get terms
        literal_mappings = chain.from_iterable(get_literal_mappings(p) for p in prefixes)

        # 2. Get mappings
        configuration = Configuration.from_prefixes(name="Diseases", prefixes=prefixes)
        mappings = configuration.get_mappings()

        # 3. Update terms and use them (i.e., to construct a grounder)
        new_literal_mappings = update_literal_mappings(literal_mappings, mappings)
        grounder = make_grounder(new_literal_mappings)

    """
    assert_projection(mappings)
    return ssslm.remap_literal_mappings(
        literal_mappings=literal_mappings,
        mappings=[(mapping.subject, mapping.object) for mapping in mappings],
    )


def _prioritization_to_curie_dict(mappings: Iterable[Mapping]) -> dict[str, str]:
    rv = {mapping.subject.curie: mapping.object.curie for mapping in mappings}
    return rv


def prioritize_df(
    mappings: list[Mapping], df: pd.DataFrame, *, column: str, target_column: str | None = None
) -> None:
    """Remap a column of a dataframe based on priority mappings."""
    assert_projection(mappings)
    curie_remapping = _prioritization_to_curie_dict(mappings)
    if target_column is None:
        target_column = f"{column}_prioritized"

    def _map_curie(curie: str) -> str:
        norm_curie = bioregistry.normalize_curie(curie)
        if norm_curie is None:
            return curie
        return curie_remapping.get(norm_curie, norm_curie)

    df[target_column] = df[column].map(_map_curie)
