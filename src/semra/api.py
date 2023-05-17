"""Semantic Mapping Reasoning Assembler."""

from __future__ import annotations

import itertools as itt
import logging
import time
from collections import Counter, defaultdict
from collections.abc import Iterable
from typing import TYPE_CHECKING

import networkx as nx
from tqdm.auto import tqdm

from semra.io import from_biomappings
from semra.rules import BROAD_MATCH, CLOSE_MATCH, DB_XREF, EXACT_MATCH, FLIP, NARROW_MATCH
from semra.struct import (
    Evidence,
    Mapping,
    MutatedEvidence,
    ReasonedEvidence,
    Reference,
    Triple,
    triple_key,
)

if TYPE_CHECKING:
    pass

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
    dd = defaultdict(list)
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
        evidence=[
            MutatedEvidence(
                type="mutated",
                evidence=evidence,
                justification=Reference(prefix="semapv", identifier="FlippedMatching"),
            )
            for evidence in mapping.evidence
        ],
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


def infer_chains(mappings: list[Mapping], *, backwards: bool = True, progress: bool = True) -> list[Mapping]:
    """Apply graph-based reasoning over mapping chains to infer new mappings.

    :param mappings: A list of input mappings
    :param backwards: Should inference be done in reverse?
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
            for path in nx.all_simple_edge_paths(sg, s, o, cutoff=5):
                predicates = [sg[u][v][PREDICATE_KEY] for u, v in path]
                p = _condense_predicates(predicates)
                if p:
                    evidence = ReasonedEvidence(
                        justification=Reference.from_curie("semapv:ComplexMapping"),
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
                    new_mappings.append(
                        Mapping(
                            s=s,
                            p=p,
                            o=o,
                            evidence=[evidence],
                        )
                    )
                    if backwards:
                        new_mappings.append(
                            Mapping(
                                o=s,
                                s=o,
                                p=FLIP[p],
                                evidence=[evidence],
                            )
                        )
    return [*mappings, *new_mappings]


def _log_diff(before: int, mappings: list[Mapping], *, verb: str, elapsed) -> None:
    logger.info(
        f"{verb} from {before:,} to {len(mappings):,} mappings (Δ={len(mappings) - before:,}) in %.2f seconds.",
        elapsed,
    )


def process(mappings: list[Mapping], upgrade_prefixes=None, remove_prefix_set=None) -> list[Mapping]:
    """Run a full deduplication, reasoning, and inference pipeline over a set of mappings."""
    import biomappings

    if remove_prefix_set:
        mappings = remove_prefixes(mappings, remove_prefix_set)

    start = time.time()
    negatives = from_biomappings(biomappings.load_false_mappings())
    logger.info(f"Loaded {len(negatives):,} negative mappings in %.2f seconds", time.time() - start)

    before = len(mappings)
    start = time.time()
    mappings = filter_negatives(mappings, negatives)
    _log_diff(before, mappings, verb="Filtered negative mappings", elapsed=time.time() - start)

    # deduplicate
    before = len(mappings)
    start = time.time()
    mappings = assemble_evidences(mappings)
    _log_diff(before, mappings, verb="Assembled", elapsed=time.time() - start)

    # only keep relevant prefixes
    # mappings = filter_prefixes(mappings, PREFIXES)
    # logger.debug(f"Filtered to {len(mappings):,} mappings")

    if upgrade_prefixes:
        # 2. using the assumption that primary mappings from each of these
        # resources to each other are exact matches, rewrite the prefixes
        mappings = upgrade_mutual_dbxrefs(mappings, upgrade_prefixes, confidence=0.95)

    # remove mapping between self, such as EFO-EFO
    logger.info("Removing self mappings (i.e., within a given semantic space)")
    before = len(mappings)
    start = time.time()
    mappings = filter_self_matches(mappings)
    _log_diff(before, mappings, verb="Filtered source internal", elapsed=time.time() - start)

    # remove dbxrefs
    logger.info("Removing unqualified database xrefs")
    before = len(mappings)
    start = time.time()
    mappings = [m for m in mappings if m.p not in {DB_XREF, CLOSE_MATCH}]
    _log_diff(before, mappings, verb="Filtered non-precise", elapsed=time.time() - start)

    # 3. Inference based on adding reverse relations then doing multi-chain hopping
    logger.info("Inferring reverse mappings")
    before = len(mappings)
    start = time.time()
    mappings = infer_reversible(mappings)
    _log_diff(before, mappings, verb="Inferred", elapsed=time.time() - start)

    logger.info("Inferring based on chains")
    before = len(mappings)
    time.time()
    mappings = infer_chains(mappings)
    _log_diff(before, mappings, verb="Inferred", elapsed=time.time() - start)

    # 4/5. Filtering negative
    logger.info("Filtering out negative mappings")
    before = len(mappings)
    start = time.time()
    mappings = filter_negatives(mappings, negatives)
    _log_diff(before, mappings, verb="Filtered negative mappings", elapsed=time.time() - start)

    # filter out self mappings again, just in case
    mappings = filter_self_matches(mappings)

    return mappings


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


def upgrade_dbxrefs(
    mappings: Iterable[Mapping], pairs: dict[tuple[str, str], float] | Iterable[tuple[str, str]]
) -> list[Mapping]:
    """Upgrade database cross-references into exact matches for the given pairs.

    :param mappings: A list of mappings
    :param pairs: A dictionary of source/target prefix pairs to the confidence of upgrading dbxrefs.
        If giving a collection of pairs, will assume a default confidence of 0.7.
    :return: A new list of mappings containing upgrades
    """
    if not isinstance(pairs, dict):
        pairs = {pair: 0.7 for pair in pairs}
    return mutate_predicate(
        mappings,
        pairs=pairs,
        old=DB_XREF,
        new=EXACT_MATCH,
        justification=Reference(prefix="semapv", identifier="UpgradeDbXrefs"),
    )


def upgrade_mutual_dbxrefs(mappings: Iterable[Mapping], prefixes: set[str], confidence: float = 1.0) -> list[Mapping]:
    pairs = {(s, t): confidence for s, t in itt.product(prefixes, repeat=2) if s != t}
    return upgrade_dbxrefs(mappings, pairs=pairs)


def mutate_predicate(
    mappings: Iterable[Mapping],
    pairs: dict[tuple[str, str], float],
    old: Reference,
    new: Reference,
    justification: Reference,
) -> list[Mapping]:
    rv = []
    for mapping in tqdm(mappings, unit_scale=True, unit="mapping", desc="Mutating predicates"):
        confidence = pairs.get((mapping.s.prefix, mapping.o.prefix))
        if confidence is not None and mapping.p == old:
            nm = Mapping(
                s=mapping.s,
                p=new,
                o=mapping.o,
                evidence=[
                    MutatedEvidence(
                        evidence=evidence,
                        justification=justification,
                        confidence_factor=confidence,
                    )
                    for evidence in mapping.evidence
                ],
            )
            rv.append(nm)
        else:
            rv.append(mapping)
    return rv


def filter_prefixes(mappings: Iterable[Mapping], prefixes: Iterable[str], *, progress: bool = True) -> list[Mapping]:
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


def filter_negatives(mappings: list[Mapping], negatives: list[Mapping]) -> list[Mapping]:
    """Filter out mappings that have been explicitly labeled as negative."""
    positive_index = get_index(mappings)
    negative_index = get_index(negatives)
    new_positive_index = {
        mapping: evidence
        for mapping, evidence in tqdm(
            positive_index.items(),
            unit_scale=True,
            unit="mapping",
            desc="Filtering negative mappings",
        )
        if mapping not in negative_index
    }
    return unindex(new_positive_index)


def project(
    mappings: list[Mapping], source_prefix: str, target_prefix: str, *, return_sus: bool = False
) -> list[Mapping]:
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
    if sus_mappings:
        logger.info("Got %d non-bijective mappings", len(sus_mappings))
        logger.info(index_str(get_index(sus_mappings)))
    rv = assemble_evidences(rv)
    if return_sus:
        return rv, sus_mappings
    return rv


def project_dict(mappings: list[Mapping], source_prefix: str, target_prefix: str) -> dict[str, str]:
    """Get a dictionary from source identifiers to target identifiers."""
    mappings = project(mappings, source_prefix, target_prefix)
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
    logger.info("Prioritized from %d original (%d exact) to %d", original_mappings, exact_mappings, end_mappings)
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
        # TODO multiple... I guess let's just return the first
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
        if not bioregistry.is_valid_identifier(mapping.o.prefix, mapping.o.identifier):
            raise ValueError(
                f"invalid mapping object: {mapping}. Use regex {bioregistry.get_pattern(mapping.o.prefix)}"
            )


def df_to_mappings(
    df,
    *,
    source_prefix: str,
    target_prefix: str,
    evidence: Evidence,
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
            evidence=[evidence],
        )
        for source_id, target_id in df[[source_identifier_column, target_identifier_column]].values
    ]
