"""Supports landscape analysis."""

import typing as t
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import bioregistry
import matplotlib.pyplot as plt
import networkx as nx
import pandas as pd
import pyobo
import seaborn as sns
import upsetplot

from semra import Configuration
from semra.api import get_index, to_multidigraph
from semra.io import _safe_get_version, from_pickle
from semra.rules import DB_XREF, EXACT_MATCH
from semra.struct import Mapping

__all__ = [
    "get_directed_index",
    "draw_counter",
    "counter_to_df",
    "landscape_analysis",
    "get_symmetric_counts_df",
    "overlap_analysis",
]


DirectedIndex = t.Dict[t.Tuple[str, str], t.Set[str]]
XXCounter = t.Counter[t.Tuple[str, str]]
XXTerms = t.Mapping[str, t.Mapping[str, str]]


@dataclass
class OverlapResults:
    """Results from mapping analysis."""

    raw_mappings: t.List[Mapping]
    raw_counts_df: pd.DataFrame
    mappings: t.List[Mapping]
    counts: XXCounter
    counts_df: pd.DataFrame
    gains_df: pd.DataFrame
    percent_gains_df: pd.DataFrame
    counts_drawing: bytes = field(init=False)

    def __post_init__(self) -> None:
        """Initialize the object by creating a drawing of the counter."""
        self.counts_drawing = draw_counter(self.counts, cls=nx.Graph, minimum_count=20)

    def write(self, directory: t.Union[str, Path]) -> None:
        """Write the tables and charts to a directory."""
        directory = Path(directory).resolve()
        self.counts_df.to_csv(directory / "counts.tsv", sep="\t", index=True)
        self.raw_counts_df.to_csv(directory / "raw_counts.tsv", sep="\t", index=True)
        with open(directory / "disease_graph.svg", "wb") as file:
            file.write(self.counts_drawing)


def overlap_analysis(configuration: Configuration, terms) -> OverlapResults:
    """Run overlap analysis."""
    raw_mappings = from_pickle(configuration.raw_pickle_path)
    raw_index = get_directed_index(raw_mappings)
    _, raw_counts_df = get_symmetric_counts_df(raw_index, terms, priority=configuration.priority)

    mappings = from_pickle(configuration.processed_pickle_path)
    directed = get_directed_index(mappings)
    counts, counts_df = get_symmetric_counts_df(directed, terms, priority=configuration.priority)

    gains_df = counts_df - raw_counts_df
    percent_gains_df = 100.0 * (counts_df - raw_counts_df) / raw_counts_df

    return OverlapResults(
        raw_mappings=raw_mappings,
        raw_counts_df=raw_counts_df,
        mappings=mappings,
        counts=counts,
        counts_df=counts_df,
        gains_df=gains_df,
        percent_gains_df=percent_gains_df,
    )


def get_terms(priority: t.List[str], subsets: t.Mapping[str, t.Collection[str]]) -> XXTerms:
    """Get the set of identifiers for each of the resources."""
    terms = {}
    for prefix in priority:
        id_name_mapping = pyobo.get_id_name_mapping(prefix)
        subset = {
            descendant
            for parent_curie in subsets.get(prefix, [])
            for descendant in pyobo.get_descendants(parent_curie) or []
        }
        if subset:
            terms[prefix] = {luid: name for luid, name in id_name_mapping.items() if f"{prefix}:{luid}" in subset}
        else:
            terms[prefix] = id_name_mapping
    return terms


def get_summary_df(priority: t.List[str], terms: XXTerms) -> pd.DataFrame:
    summary_rows = [
        (prefix, bioregistry.get_license(prefix), _safe_get_version(prefix), len(terms.get(prefix, [])))
        for prefix in priority
    ]
    return pd.DataFrame(summary_rows, columns=["prefix", "license", "version", "terms"])


def get_directed_index(mappings: t.Iterable[Mapping]) -> DirectedIndex:
    index = get_index(mappings, progress=False)
    directed: t.DefaultDict[t.Tuple[str, str], t.Set[str]] = defaultdict(set)
    target_predicates = {EXACT_MATCH, DB_XREF}
    for s, p, o in index:
        if p in target_predicates:
            directed[s.prefix, o.prefix].add(s.identifier)
            directed[o.prefix, s.prefix].add(o.identifier)
    return dict(directed)


def get_asymmetric_counts_df(directed: DirectedIndex, terms: XXTerms, priority: t.List[str]):
    asymmetric_counts = Counter()
    for (l, r), l_entities in directed.items():
        l_terms = terms.get(l)
        if l_terms:
            count = len(l_entities.intersection(l_terms))
        else:
            count = len(l_entities)
        asymmetric_counts[l, r] = count

    df = counter_to_df(asymmetric_counts, priority=priority, default=0).fillna(0).astype(int)
    return asymmetric_counts, df


def get_asymmetric_percents_df(asymmetric_counts, terms: XXTerms, priority: t.List[str]):
    """
    The following summary looks for each ordered pair of resources, what
    percentage of each resources' terms are mapped to the other resource.
    Because each resource is a different size, this is an asymmetric measurement.

    The way to read this table is the horizontal index corresponds to the
    source prefix and the columns correspond to the target prefix. This means
    in the row with label "efo" and column with label "mesh" that has 14% means
    that 14% of EFO can be mapped to MeSH.

    SVG(draw_counter(asymmetric, count_format=".1%"))

    (asymmetric_summary_df * 100).round(2)
    """
    asymmetric = Counter()
    for (l, r), count in asymmetric_counts.items():
        denominator = len(terms.get(l, []))
        asymmetric[l, r] = count / denominator if denominator > 0 else None

    df = counter_to_df(asymmetric, priority=priority)
    return df, asymmetric


def get_symmetric_counts_df(
    directed: DirectedIndex, terms: XXTerms, priority: t.List[str]
) -> t.Tuple[XXCounter, pd.DataFrame]:
    counter: XXCounter = Counter()

    for left_prefix, right_prefix in directed:
        left = directed[left_prefix, right_prefix]
        if left_terms := terms.get(left_prefix, []):
            left.intersection_update(left_terms)
        right = directed[right_prefix, left_prefix]
        if right_terms := terms.get(right_prefix, []):
            right.intersection_update(right_terms)
        counter[left_prefix, right_prefix] = max(len(left), len(right))

    for prefix in priority:
        tt = terms.get(prefix, [])
        if tt:
            counter[prefix, prefix] = len(tt)

    df = counter_to_df(counter, priority=priority, default=0).fillna(0).astype(int)
    return counter, df


def get_symmetric_percents_df(symmetric_counts, terms: XXTerms, priority: t.List[str]):
    """

    # clip since there might be some artifacts of mappings to terms that don't exist anymore
    (symmetric_df * 100).round(3)
    SVG(draw_counter(symmetric, cls=nx.Graph, count_format=".2%", minimum_count=0.01))
    """
    # intersect with the terms for each to make sure we're not keeping any mappings that are irrelevant
    symmetric = Counter()
    for (l, r), count in symmetric_counts.items():
        # FIXME - estimate terms lists based on what appears in the mappings
        if terms[r] and terms[l]:
            denom = max(len(terms[r]), len(terms[l]))
        elif terms[r]:
            denom = len(terms[r])
        elif terms[l]:
            denom = len(terms[l])
        else:
            denom = None
            continue
        symmetric[l, r] = count / denom

    symmetric_df = counter_to_df(symmetric, priority=priority).fillna(0.0)
    return symmetric, symmetric_df


def draw_counter(
    counter: XXCounter,
    scaling_factor: float = 3.0,
    count_format=",",
    cls: t.Type[nx.Graph] = nx.DiGraph,
    minimum_count: float = 0.0,
    prog: str = "dot",
    output_format: str = "svg",
    direction: str = "LR",
) -> bytes:
    """Draw a source/target prefix pair counter as a network."""
    graph = cls()
    for (source_prefix, target_prefix), count in counter.items():
        if not count:
            continue
        if count <= minimum_count:
            continue
        graph.add_edge(source_prefix, target_prefix, label=f"{count:{count_format}}")

    agraph = nx.nx_agraph.to_agraph(graph)
    agraph.graph_attr["rankdir"] = direction

    values = [v for v in counter.values() if v is not None and v > 0]
    bottom, top = min(values), max(values)
    rr = top - bottom

    for edge, weight in counter.items():
        if not weight:
            continue
        x = 1 + scaling_factor * (weight - bottom) / rr
        if agraph.has_edge(*edge):
            agraph.get_edge(*edge).attr["penwidth"] = x
    return agraph.draw(prog=prog, format=output_format)


def counter_to_df(
    counter: XXCounter, priority: t.List[str], default: float = 1.0, drop_missing: bool = True
) -> pd.DataFrame:
    """Get a dataframe from a counter."""
    rows = [[counter.get((p1, p2), None) for p2 in priority] for p1 in priority]
    df = pd.DataFrame(rows, columns=priority, index=priority)
    if drop_missing:
        df = df.dropna(axis=1, how="all")
        df = df.dropna(axis=0, how="all")

    df.index.name = "source_prefix"
    df.columns.name = "target_prefix"
    return df


def _get_counter(mappings: t.Iterable[Mapping]) -> t.Counter[t.FrozenSet[str]]:
    """Get a counter where the keys are the set of all prefixes in a weakly connected component."""
    counter = Counter()
    graph = to_multidigraph(mappings)
    for component in nx.weakly_connected_components(graph):
        prefixes = frozenset(r.prefix for r in component)
        counter[prefixes] += 1
    return counter


def _index_entities(mappings: t.Iterable[Mapping]) -> t.Dict[str, t.Set[str]]:
    entities = defaultdict(set)
    for mapping in mappings:
        for reference in (mapping.s, mapping.o):
            entities[reference.prefix].add(reference.identifier)
    return dict(entities)


def landscape_analysis(mappings: t.List[Mapping], terms: XXTerms, priority: t.List[str]):
    entities = _index_entities(mappings)
    counter = _get_counter(mappings)

    #: A count of the number of entities that have at least mapping.
    #: This is calculated by the appearance of a weakly connected component
    #: in :func:`_get_counter`. This needs to be calculated before enriching
    #: the resulting counter object with entities that don't appear in mappings
    at_least_1_mapping = sum(counter.values())

    unique_to_single = Counter()
    for prefix in priority:
        prefix_terms = terms.get(prefix)
        if not prefix_terms:
            continue

        prefix_terms_set = set(prefix_terms)
        mapped_terms: t.Set[str] = entities[prefix]
        counter[frozenset([prefix])] = unique_to_single[prefix] = len(prefix_terms_set - mapped_terms)

    #: A count of the number of entities that have no mappings.
    #: This is calculated based on the set difference between entities
    #: appearing in mappings and the preloaded terms lists
    only_1_mapping = sum(unique_to_single.values())

    #: A count of the number of entities appearing in _all_ resources.
    #: Also calculated the same way with :func:`_get_counter`
    conserved = counter[frozenset(priority)]

    #: A counter of the number of entities that either have mappings or not.
    #: This is only an estimate and is susceptible to a few things:
    #:
    #: 1. It can be artificially high because there are entities that _should_ be mapped, but are not
    #: 2. It can be artificially low because there are entities that are incorrectly mapped, e.g., as
    #:    a result of inference. The frontend curation interface can help identify and remove these
    #: 3. It can be artificially low because for some vocabularies like SNOMED-CT, it's not possible
    #:    to load a terms list, and therefore it's not possible to account for terms that aren't mapped
    #: 4. It can be artificially high if a vocabulary is used that covers many domains and is not properly
    #:    subset'd. For example, EFO covers many different domains, so when doing disease landscape
    #:    analysis, it should be subset to only terms in the disease hierarchy (i.e., appearing under
    #:    ``efo:0000408``).
    total_entity_estimate = sum(counter.values())

    return LandscapeResult(
        at_least_1_mapping=at_least_1_mapping,
        only_1_mapping=only_1_mapping,
        total_entity_estimate=total_entity_estimate,
        conserved=conserved,
        priority=priority,
        counter=counter,
    )


@dataclass
class LandscapeResult:
    """Describes results of landscape analysis."""

    priority: t.List[str]
    at_least_1_mapping: int
    only_1_mapping: int
    conserved: int
    total_entity_estimate: int
    counter: t.Counter[t.FrozenSet[str]]

    def describe(self) -> str:
        """Describe the results in English prose."""
        return (
            f"This estimates a total of {self.total_entity_estimate:,} unique entities.\n"
            f"Of these, {self.at_least_1_mapping:,} ({self.at_least_1_mapping/self.total_entity_estimate:.1%}) have "
            f"at least one mapping.\n{self.only_1_mapping:,} ({self.only_1_mapping/self.total_entity_estimate:.1%}) "
            f"are unique to a single resource.\n{self.conserved:,} ({self.conserved/self.total_entity_estimate:.1%}) "
            f"appear in all {len(self.priority)} resources.\n\nThis estimate is susceptible to several caveats:\n\n"
            "- Missing mappings inflates this measurement\n"
            "- Generic resources like MeSH contain irrelevant entities that can't be mapped\n"
        )

    def get_upset_df(self) -> pd.DataFrame:
        return upsetplot.from_memberships(*zip(*self.counter.most_common()))

    def plot_upset(self):
        """Plot the results with an UpSet plot."""
        example = self.get_upset_df()
        """Here's what the output from upsetplot.plot looks like:

        {'matrix': <Axes: >,
         'shading': <Axes: >,
         'totals': <Axes: >,
         'intersections': <Axes: ylabel='Intersection size'>}
        """
        plot_result = upsetplot.plot(
            example,
            # show_counts=True,
        )
        plot_result["intersections"].set_yscale("log")
        plot_result["intersections"].set_ylim([1, plot_result["intersections"].get_ylim()[1]])
        # plot_result["totals"].set_xlabel("Size")
        mm, _ = plot_result["totals"].get_xlim()
        plot_result["totals"].set_xlim([mm, 1])
        plot_result["totals"].set_xscale("log")  # gets domain error

    def get_distribution(self) -> t.Counter[int]:
        """Get the distribution."""
        counter = Counter()
        for prefixes, count in self.counter.items():
            counter[len(prefixes)] += count

        # Back-fill any intermediate counts with zero
        max_key = max(counter)
        for i in range(1, max_key):
            if i not in counter:
                counter[i] = 0

        return counter

    def plot_distribution(
        self,
        height: float = 2.7,
        width_ratio: float = 0.65,
        top_ratio: float = 20.0,
    ) -> None:
        vv = self.get_distribution()
        fig, ax = plt.subplots(figsize=(len(vv) * width_ratio, height))
        sns.barplot(vv, ax=ax)

        for index, value in vv.items():
            plt.text(
                index - 1, value + 0.2, f"{value:,}\n({value/self.total_entity_estimate:.1%})", ha="center", va="bottom"
            )

        ax.set_xlabel("# Resources a Concept Appears in")
        ax.set_ylabel("Count")
        ax.set_title(f"Landscape of {self.total_entity_estimate:,} Unique Concepts")
        ax.set_yscale("log")
        # since we're in a log scale, pad half of the max value to the top to make sure
        # the counts fit in the box
        a, b = ax.get_ylim()
        ax.set_ylim([a, b + top_ratio * max(vv.values())])
