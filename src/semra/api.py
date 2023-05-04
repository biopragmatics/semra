"""Semantic Mapping Reasoning Assembler."""

from __future__ import annotations

import itertools as itt
import logging
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable, TextIO

import bioregistry
import click
import networkx as nx
import pandas as pd
from tqdm.auto import tqdm

from semra.rules import BROAD_MATCH, DB_XREF, EQUIVALENT_TO, EXACT_MATCH, FLIP, NARROW_MATCH
from semra.sources import from_biomappings
from semra.struct import (
    Evidence,
    Mapping,
    MutatedEvidence,
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


def count_source_target(mappings: list[Mapping]) -> Counter[tuple[str, str]]:
    """Count source prefix-target prefix pairs."""
    return Counter((s.prefix, o.prefix) for s, _, o in get_index(mappings))


def get_index(mappings: list[Mapping]) -> Index:
    """Aggregate and deduplicate evidences for each core triple."""
    dd = defaultdict(list)
    for mapping in mappings:
        dd[mapping.triple].extend(mapping.evidence)
    return {triple: deduplicate_evidence(evidence) for triple, evidence in dd.items()}


def assemble_evidences(mappings: list[Mapping]) -> list[Mapping]:
    index = get_index(mappings)
    return unindex(index)


def infer_reversible(mappings: list[Mapping]) -> list[Mapping]:
    rv = []
    for mapping in mappings:
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
    return [
        _from_edge(graph, s, o)
        for s, o in graph.edges()
    ]

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


def infer_chains(mappings: list[Mapping], *, backwards: bool = True) -> list[Mapping]:
    """Apply graph-based reasoning over mapping chains to infer new mappings.

    :param mappings: A list of input mappings
    :param backwards: Should inference be done in reverse?
    :return: The list of input mappings _plus_ inferred mappings
    """
    mappings = assemble_evidences(mappings)
    graph = to_graph(mappings)
    new_edges = []
    components = sorted(nx.weakly_connected_components(graph), key=len, reverse=True)
    it = tqdm(components, unit="component", desc="Inferring chains", unit_scale=True)
    for _i, component in enumerate(it):
        sg: nx.DiGraph = graph.subgraph(component).copy()
        for s, o in itt.combinations(sg, 2):
            if sg.has_edge(s, o):  # do not overwrite existing mappings
                continue
            # TODO there has to be a way to reimplement transitive closure to handle this
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
                    new_edges.append(
                        (
                            s,
                            o,
                            {
                                PREDICATE_KEY: p,
                                EVIDENCE_KEY: [evidence],
                            },
                        )
                    )
                    if backwards:
                        new_edges.append(
                            (
                                o,
                                s,
                                {
                                    PREDICATE_KEY: FLIP[p],
                                    EVIDENCE_KEY: [evidence],
                                },
                            )
                        )
    graph.add_edges_from(new_edges)
    return from_graph(graph)


def _log_debug_diff(before: int, mappings: list[Mapping], *, verb: str) -> None:
    logger.debug(f"{verb} from {before:,} to {len(mappings):,} mappings (Δ={len(mappings) - before:,})")


def process(mappings: list[Mapping], upgrade_prefixes=None) -> list[Mapping]:
    """Run a full deduplication, reasoning, and inference pipeline over a set of mappings."""
    import biomappings

    negatives = from_biomappings(biomappings.load_false_mappings())
    logger.debug(f"Loaded {len(negatives):,} negative mappings")

    before = len(mappings)
    mappings = filter_negatives(mappings, negatives)
    _log_debug_diff(before, mappings, verb="Filtered negative mappings")

    # deduplicate
    before = len(mappings)
    mappings = assemble_evidences(mappings)
    _log_debug_diff(before, mappings, verb="Assembled")

    # only keep relevant prefixes
    # mappings = filter_prefixes(mappings, PREFIXES)
    # logger.debug(f"Filtered to {len(mappings):,} mappings")

    if upgrade_prefixes:
        # 2. using the assumption that primary mappings from each of these
        # resources to each other are exact matches, rewrite the prefixes
        mappings = upgrade_mutual_dbxrefs(mappings, upgrade_prefixes)

    # remove mapping between self, such as EFO-EFO
    logger.debug("Removing self mappings (i.e., within a given semantic space)")
    before = len(mappings)
    mappings = filter_self_matches(mappings)
    _log_debug_diff(before, mappings, verb="Filtered")

    # remove dbxrefs
    logger.debug("Removing unqualified database xrefs")
    before = len(mappings)
    mappings = [m for m in mappings if m.p != DB_XREF]
    _log_debug_diff(before, mappings, verb="Filtered")

    # 3. Inference based on adding reverse relations then doing multi-chain hopping
    logger.debug("Inferring reverse mappings")
    before = len(mappings)
    mappings = infer_reversible(mappings)
    _log_debug_diff(before, mappings, verb="Inferred")

    logger.debug("Inferring based on chains")
    before = len(mappings)
    mappings = infer_chains(mappings)
    _log_debug_diff(before, mappings, verb="Inferred")

    # 4/5. Filtering negative
    click.echo("Filtering out negative mappings")
    before = len(mappings)
    mappings = filter_negatives(mappings, negatives)
    _log_debug_diff(before, mappings, verb="Filtered negative mappings")
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


def upgrade_dbxrefs(mappings: Iterable[Mapping], pairs: set[tuple[str, str]]) -> list[Mapping]:
    return mutate_predicate(
        mappings,
        pairs=pairs,
        old=DB_XREF,
        new=EXACT_MATCH,
        justification=Reference(prefix="semapv", identifier="UpgradeDbXrefs"),
    )


def upgrade_mutual_dbxrefs(mappings: Iterable[Mapping], prefixes: set[str]) -> list[Mapping]:
    pairs = {(s, t) for s, t in itt.product(prefixes, repeat=2) if s != t}
    return upgrade_dbxrefs(mappings, pairs=pairs)


def mutate_predicate(
    mappings: Iterable[Mapping], pairs: set[tuple[str, str]], old: Reference, new: Reference, justification: Reference
) -> list[Mapping]:
    rv = []
    for mapping in mappings:
        if (mapping.s.prefix, mapping.o.prefix) in pairs and mapping.p == old:
            nm = Mapping(
                s=mapping.s,
                p=new,
                o=mapping.o,
                evidence=[
                    MutatedEvidence(
                        evidence=evidence,
                        justification=justification,
                    )
                    for evidence in mapping.evidence
                ],
            )
            rv.append(nm)
        else:
            rv.append(mapping)
    return rv


def filter_prefixes(mappings: Iterable[Mapping], prefixes: Iterable[str]) -> list[Mapping]:
    """Filter out mappings whose subject or object are not in the given list of prefixes."""
    prefixes = set(prefixes)
    return [mapping for mapping in mappings if mapping.s.prefix in prefixes and mapping.o.prefix in prefixes]


def filter_self_matches(mappings: Iterable[Mapping]) -> list[Mapping]:
    """Filter out mappings within the same resource."""
    return [mapping for mapping in mappings if mapping.s.prefix != mapping.o.prefix]


def filter_negatives(mappings: list[Mapping], negatives: list[Mapping]) -> list[Mapping]:
    """Filter out mappings that have been explicitly labeled as negative."""
    positive_index = get_index(mappings)
    negative_index = get_index(negatives)
    new_positive_index = {
        mapping: evidence for mapping, evidence in positive_index.items() if mapping not in negative_index
    }
    return unindex(new_positive_index)


def project(mappings: list[Mapping], source_prefix: str, target_prefix: str) -> list[Mapping]:
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
        logger.debug("Got 1-many mappings")
        click.echo(index_str(get_index(sus_mappings)))
    return assemble_evidences(rv)


def prioritize(mappings: list[Mapping], priority: list[str]) -> list[Mapping]:
    """Get a priority star graph.

    :param mappings:
    :param priority: A list of prefixes to prioritize. The first prefix in the list gets highest.
    """
    mappings = [m for m in mappings if m.p == EXACT_MATCH]
    graph = to_graph(mappings).to_undirected()
    rv = []
    for component in nx.connected_components(graph):
        o = _get_priority(component, priority)
        if o is None:
            continue
        rv.extend(
            _from_edge(graph, s, o)
            # TODO should this work even if s-o edge not exists?
            #  can also do "inference" here
            for s in component
            if s != o
        )

    # sort such that the mappings are ordered by object by priority order
    # then identifier of object, then subject prefix in alphabetical order
    pos = {prefix: i for i, prefix in enumerate(priority)}
    rv = sorted(rv, key=lambda m: (pos[m.o.prefix], m.o.identifier, m.s.prefix, m.s.identifier))
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


def get_sssom_df(mappings: list[Mapping]) -> pd.DataFrame:
    rows = [_get_sssom_row(m, e) for m in mappings for e in m.evidence]
    columns = ["subject_id", "predicate_id", "object_id", "mapping_justification", "mapping_set", "author_id"]
    return pd.DataFrame(rows, columns=columns)


def _get_sssom_row(mapping: Mapping, e):
    # TODO increase this
    return (
        mapping.s.curie,
        mapping.p.curie,
        mapping.o.curie,
        e.justification.curie if e.justification else "",
        e.mapping_set or "",
        e.author.curie if e.author else "",
    )


def write_sssom(mappings: list[Mapping], file: str | Path | TextIO) -> None:
    df = get_sssom_df(mappings)
    df.to_csv(file, sep="\t", index=False)


def unindex(index: Index) -> list[Mapping]:
    return [Mapping.from_triple(triple, evidence=evidence) for triple, evidence in index.items()]


def deduplicate_evidence(evidence: list[Evidence]) -> list[Evidence]:
    d = {e.key(): e for e in evidence}
    return list(d.values())


def validate_mappings(mappings: list[Mapping]) -> None:
    for mapping in tqdm(mappings, desc="validating", unit_scale=True, unit="mapping"):
        if bioregistry.normalize_prefix(mapping.s.prefix) != mapping.s.prefix:
            raise ValueError(f"invalid subject prefix: {mapping}.")
        if bioregistry.normalize_prefix(mapping.o.prefix) != mapping.o.prefix:
            raise ValueError(f"invalid object prefix: {mapping}.")
        if not bioregistry.is_valid_identifier(mapping.s.prefix, mapping.s.identifier):
            raise ValueError(
                f"invalid mapping subject: {mapping}. Use regex {bioregistry.get_pattern(mapping.o.prefix)}"
            )
        if not bioregistry.is_valid_identifier(mapping.o.prefix, mapping.o.identifier):
            raise ValueError(
                f"invalid mapping object: {mapping}. Use regex {bioregistry.get_pattern(mapping.o.prefix)}"
            )
