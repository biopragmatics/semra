"""Semantic Mapping Reasoning Assembler."""

from __future__ import annotations

import itertools as itt
import logging
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable
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
    ReasonedEvidence,
    Reference,
    Triple,
    triple_key,
)

logger = logging.getLogger(__name__)

PREDICATE_KEY = "predicate"
EVIDENCE_KEY = "evidence"

#: An index allows for the aggregation of evidences for each core triple
Index = dict[Triple, list[Evidence]]


def count_source_target(mappings: Iterable[Mapping]) -> Counter[tuple[str, str]]:
    """Count source prefix-target prefix pairs."""
    return Counter((s.prefix, o.prefix) for s, _, o in get_index(mappings))


def str_source_target_counts(mappings: Iterable[Mapping], minimum: int = 0) -> str:
    from tabulate import tabulate

    so_prefix_counter = count_source_target(mappings)
    return tabulate(
        [(s, o, c) for (s, o), c in so_prefix_counter.most_common() if c > minimum],
        headers=["source prefix", "target prefix", "count"],
        tablefmt="github",
    )


def print_source_target_counts(mappings: Iterable[Mapping], minimum: int = 0) -> None:
    print(str_source_target_counts(mappings=mappings, minimum=minimum))  # noqa:T201


def get_index(mappings: Iterable[Mapping], *, progress: bool = True) -> Index:
    """Aggregate and deduplicate evidences for each core triple."""
    dd: defaultdict[Triple, list[Evidence]] = defaultdict(list)
    for mapping in tqdm(mappings, unit="mapping", unit_scale=True, desc="Indexing mappings", disable=not progress):
        dd[mapping.triple].extend(mapping.evidence)
    return {triple: deduplicate_evidence(evidence) for triple, evidence in dd.items()}


def assemble_evidences(mappings: list[Mapping], *, progress: bool = True) -> list[Mapping]:
    index = get_index(mappings, progress=progress)
    return unindex(index, progress=progress)


def infer_reversible(mappings: list[Mapping], *, progress: bool = True) -> list[Mapping]:
    rv = []
    for mapping in tqdm(mappings, unit="mapping", unit_scale=True, desc="Infer reverse", disable=not progress):
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


def to_graph(mappings: list[Mapping]) -> nx.DiGraph:
    """Convert mappings into a directed graph data model."""
    graph = nx.DiGraph()
    for mapping in mappings:
        graph.add_edge(
            mapping.s,
            mapping.o,
            **{PREDICATE_KEY: mapping.p, EVIDENCE_KEY: mapping.evidence},
        )
    return graph


def from_graph(graph: nx.DiGraph) -> list[Mapping]:
    """Extract mappings from a directed graph data model."""
    return [_from_edge(graph, s, o) for s, o in graph.edges()]


def _from_edge(graph: nx.DiGraph, s: Reference, o: Reference) -> Mapping:
    data = graph[s][o]
    return Mapping(s=s, p=data[PREDICATE_KEY], o=o, evidence=data[EVIDENCE_KEY])


def _condense_predicates(predicates: list[Reference]) -> Reference | None:
    predicate_set = set(predicates)
    if predicate_set == {EXACT_MATCH}:
        return EXACT_MATCH
    if predicate_set == {BROAD_MATCH} or predicate_set == {EXACT_MATCH, BROAD_MATCH}:
        return BROAD_MATCH
    if predicate_set == {NARROW_MATCH} or predicate_set == {EXACT_MATCH, NARROW_MATCH}:
        return NARROW_MATCH
    return None


def infer_chains(
    mappings: list[Mapping], *, backwards: bool = True, progress: bool = True, cutoff: int = 5
) -> list[Mapping]:
    """Apply graph-based reasoning over mapping chains to infer new mappings.

    :param mappings: A list of input mappings
    :param backwards: Should inference be done in reverse?
    :param cutoff: What's the maximum length path to infer over?
    :return: The list of input mappings _plus_ inferred mappings
    """
    mappings = assemble_evidences(mappings, progress=progress)
    graph = to_graph(mappings)
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
                p = _condense_predicates(predicates)
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


def index_str(index: Index) -> str:
    from tabulate import tabulate

    rows = []

    def key(pair):
        return triple_key(pair[0])

    for (s, p, o), evidences in sorted(index.items(), key=key):
        if not evidences:
            rows.append((s.curie, p.curie, o.curie, ""))
        else:
            first, *rest = evidences
            rows.append((s.curie, p.curie, o.curie, first))
            for r in rest:
                rows.append(("", "", "", r))
    return tabulate(rows, headers=["s", "p", "o", "ev"], tablefmt="github")


def infer_mutual_dbxref_mutations(
    mappings: Iterable[Mapping],
    prefixes: set[str],
    confidence: float | None = None,
) -> list[Mapping]:
    pairs = {(s, t) for s, t in itt.product(prefixes, repeat=2) if s != t}
    return infer_dbxref_mutations(mappings, pairs=pairs, confidence=confidence)


def infer_dbxref_mutations(
    mappings: Iterable[Mapping],
    pairs: dict[tuple[str, str], float] | Iterable[tuple[str, str]],
    confidence: float | None = None,
) -> list[Mapping]:
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
    pairs: dict[tuple[str, str], float],
    old: Reference,
    new: Reference,
) -> list[Mapping]:
    """Infer mappings with alternate predicates for the given prefix pairs.

    :param mappings: Mappings to infer from
    :param pairs: A dictionary of pairs of (subject prefix, object prefix) to the confidence
        of inference
    :param old: The predicate on which inference should be done
    :param new: The predicate to get inferred
    :returns: A list of all old mapping plus inferred ones interspersed.
    """
    rv = []
    for mapping in tqdm(mappings, unit_scale=True, unit="mapping", desc="Adding mutated predicates"):
        rv.append(mapping)
        confidence = pairs.get((mapping.s.prefix, mapping.o.prefix))
        if confidence is not None and mapping.p == old:
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


def keep_prefixes(mappings: Iterable[Mapping], prefixes: Iterable[str], *, progress: bool = True) -> list[Mapping]:
    """Filter out mappings whose subject or object are not in the given list of prefixes."""
    prefixes = set(prefixes)
    return [
        mapping
        for mapping in tqdm(
            mappings,
            unit_scale=True,
            unit="mapping",
            desc=f"Keeping from {len(prefixes)} prefixes",
            disable=not progress,
        )
        if mapping.s.prefix in prefixes and mapping.o.prefix in prefixes
    ]


def remove_prefixes(mappings: Iterable[Mapping], prefixes: Iterable[str]) -> list[Mapping]:
    """Filter out mappings whose subject or object are in the given list of prefixes."""
    prefixes = set(prefixes)
    return [
        mapping
        for mapping in tqdm(mappings, unit_scale=True, unit="mapping", desc=f"Filtering out {len(prefixes)} prefixes")
        if mapping.s.prefix not in prefixes and mapping.o.prefix not in prefixes
    ]


def filter_self_matches(mappings: Iterable[Mapping], *, progress: bool = True) -> list[Mapping]:
    """Filter out mappings within the same resource."""
    return [
        mapping
        for mapping in tqdm(
            mappings, unit_scale=True, unit="mapping", desc="Filtering out self-matches", disable=not progress
        )
        if mapping.s.prefix != mapping.o.prefix
    ]


def filter_mappings(mappings: list[Mapping], skip_mappings: list[Mapping], *, progress: bool = True) -> list[Mapping]:
    """Filter out mappings in the second set from the first set."""
    skip_set = {m.triple for m in skip_mappings}
    return [
        mapping
        for mapping in tqdm(
            mappings,
            unit_scale=True,
            unit="mapping",
            desc="Filtering mappings",
            disable=not progress,
        )
        if mapping.triple not in skip_set
    ]


M2MIndex = defaultdict[tuple[str, str], defaultdict[str, defaultdict[str, list[Mapping]]]]


def get_many_to_many(mappings: list[Mapping]) -> list[Mapping]:
    """Get many-to-many mappings, disregarding predicate type."""
    forward: M2MIndex = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    backward: M2MIndex = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    for mapping in mappings:
        forward[mapping.s.prefix, mapping.o.prefix][mapping.s.identifier][mapping.o.identifier].append(mapping)
        backward[mapping.s.prefix, mapping.o.prefix][mapping.o.identifier][mapping.s.identifier].append(mapping)

    index: defaultdict[Triple, list[Evidence]] = defaultdict(list)
    for preindex in [forward, backward]:
        for d1 in preindex.values():
            for d2 in d1.values():
                if len(d2) > 1:  # means there are multiple identifiers mapped
                    for mapping in itt.chain.from_iterable(d2.values()):
                        index[mapping.triple].extend(mapping.evidence)

    rv = [Mapping.from_triple(triple, deduplicate_evidence(evidence)) for triple, evidence in index.items()]
    return rv


def project(
    mappings: list[Mapping], source_prefix: str, target_prefix: str, *, return_sus: bool = False
) -> list[Mapping] | tuple[list[Mapping], list[Mapping]]:
    """Ensure that each identifier only appears as the subject of one mapping."""
    subject_index = defaultdict(list)
    object_index = defaultdict(list)
    for mapping in mappings:
        if mapping.s.prefix == source_prefix and mapping.o.prefix == target_prefix:
            subject_index[mapping.s].append(mapping)
            object_index[mapping.o].append(mapping)

    rv = []
    sus_mappings = []
    for entity in {*subject_index, *object_index}:
        subject_mappings = subject_index.get(entity, [])
        if len(subject_mappings) <= 1:
            rv.extend(subject_mappings)
        else:
            sus_mappings.extend(subject_mappings)
        object_mappings = object_index.get(entity, [])
        if len(object_mappings) <= 1:
            rv.extend(object_mappings)
        else:
            sus_mappings.extend(object_mappings)
    # if sus_mappings:
    #     logger.info("Got %d non-bijective mappings", len(sus_mappings))
    #     logger.info(index_str(get_index(sus_mappings)))
    rv = assemble_evidences(rv)
    if return_sus:
        return rv, sus_mappings
    return rv


def project_dict(mappings: list[Mapping], source_prefix: str, target_prefix: str) -> dict[str, str]:
    """Get a dictionary from source identifiers to target identifiers."""
    mappings = cast(list[Mapping], project(mappings, source_prefix, target_prefix))
    return {mapping.s.identifier: mapping.o.identifier for mapping in mappings}


def prioritize(mappings: list[Mapping], priority: list[str]) -> list[Mapping]:
    """Get a priority star graph.

    :param mappings:
    :param priority: A list of prefixes to prioritize. The first prefix in the list gets highest.
    """
    original_mappings = len(mappings)
    mappings = [m for m in mappings if m.p == EXACT_MATCH]
    exact_mappings = len(mappings)

    graph = to_graph(mappings).to_undirected()
    rv: list[Mapping] = []
    for component in tqdm(nx.connected_components(graph), unit="component", unit_scale=True):
        o = _get_priority(component, priority)
        if o is None:
            continue
        rv.extend(
            _from_edge(graph, s, o)
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


def _get_priority(component: list[Reference], priority: list[str]) -> Reference | None:
    prefix_to_references = defaultdict(list)
    for c in component:
        prefix_to_references[c.prefix].append(c)
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


def unindex(index: Index, *, progress: bool = True) -> list[Mapping]:
    """Convert a mapping index into a list of mapping objects."""
    return [
        Mapping.from_triple(triple, evidence=evidence)
        for triple, evidence in tqdm(
            index.items(), unit_scale=True, unit="mapping", desc="Unindexing mappings", disable=not progress
        )
    ]


def deduplicate_evidence(evidence: list[Evidence]) -> list[Evidence]:
    """Deduplicate a list of evidences based on their "key" function."""
    d = {e.key(): e for e in evidence}
    return list(d.values())


def validate_mappings(mappings: list[Mapping]) -> None:
    """Validate mappings against the Bioregistry and raise an error on the first invalid."""
    import bioregistry

    for mapping in tqdm(mappings, desc="Validating mappings", unit_scale=True, unit="mapping"):
        if bioregistry.normalize_prefix(mapping.s.prefix) != mapping.s.prefix:
            raise ValueError(f"invalid subject prefix: {mapping}.")
        if bioregistry.normalize_prefix(mapping.o.prefix) != mapping.o.prefix:
            raise ValueError(f"invalid object prefix: {mapping}.")
        if not bioregistry.is_valid_identifier(mapping.s.prefix, mapping.s.identifier):
            raise ValueError(
                f"invalid mapping subject: {mapping}. Use regex {bioregistry.get_pattern(mapping.s.prefix)}"
            )
        if ":" in mapping.s.identifier:
            raise ValueError(f"banana in mapping subject: {mapping}")
        if not bioregistry.is_valid_identifier(mapping.o.prefix, mapping.o.identifier):
            raise ValueError(
                f"invalid mapping object: {mapping}. Use regex {bioregistry.get_pattern(mapping.o.prefix)}"
            )
        if ":" in mapping.o.identifier:
            raise ValueError(f"banana in mapping object: {mapping}")


def df_to_mappings(
    df,
    *,
    source_prefix: str,
    target_prefix: str,
    evidence: Callable[[], Evidence],
    source_identifier_column: str | None = None,
    target_identifier_column: str | None = None,
) -> list[Mapping]:
    if source_identifier_column is None:
        source_identifier_column = source_prefix
    if target_identifier_column is None:
        target_identifier_column = target_prefix
    return [
        Mapping(
            s=Reference(prefix=source_prefix, identifier=source_id),
            p=EXACT_MATCH,
            o=Reference(prefix=target_prefix, identifier=target_id),
            evidence=[evidence()],
        )
        for source_id, target_id in tqdm(
            df[[source_identifier_column, target_identifier_column]].values,
            unit="mapping",
            unit_scale=True,
            desc=f"Processing {source_prefix}",
        )
    ]


def summarize_prefixes(mappings: list[Mapping]) -> pd.DataFrame:
    """Get a dataframe summarizing the prefixes appearing in the mappings."""
    import bioregistry

    prefixes = set(itt.chain.from_iterable((m.o.prefix, m.s.prefix) for m in mappings))
    return pd.DataFrame(
        [(prefix, bioregistry.get_name(prefix), bioregistry.get_description(prefix)) for prefix in sorted(prefixes)],
        columns=["prefix", "name", "description"],
    ).set_index("prefix")
