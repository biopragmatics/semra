"""Summary tools."""

from __future__ import annotations

import typing as t
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from textwrap import dedent
from typing import cast

import bioregistry
import networkx as nx
import pandas as pd

from semra.api import (
    DirectedIndex,
    PrefixIdentifierDict,
    SymmetricCounter,
    _count_terms,
    count_component_sizes,
    filter_subsets,
    get_directed_index,
    get_observed_terms,
    get_symmetric_counter,
    get_terms,
)
from semra.pipeline import Configuration
from semra.rules import DB_XREF, EXACT_MATCH, SubsetConfiguration
from semra.struct import Mapping

__all__ = [
    "LandscapeResult",
    "OverlapResults",
    "Summarizer",
]


class Summarizer:
    """An object that encapsulates the state for the overlap analysis."""

    def __init__(self, configuration: Configuration, *, show_progress: bool = False) -> None:
        """Initialize the summarizer wrapper."""
        self.configuration = configuration

        self.terms_exact = get_terms(
            configuration.priority, configuration.subsets, show_progress=show_progress
        )

        self.raw_mappings = configuration.read_raw_mappings()
        self.processed_mappings = configuration.read_processed_mappings()
        if configuration.subsets:
            hydrated_subsets = configuration.get_hydrated_subsets(show_progress=show_progress)
            self.raw_mappings = filter_subsets(self.raw_mappings, hydrated_subsets)
            self.processed_mappings = filter_subsets(self.processed_mappings, hydrated_subsets)

        self.terms_observed = get_observed_terms(self.processed_mappings)

    def get_summary_df(self) -> pd.DataFrame:
        """Get a summary dataframe."""
        return get_summary_df(
            prefixes=self.configuration.priority,
            subsets=self.configuration.subsets,
            terms_exact=self.terms_exact,
            terms_observed=self.terms_observed,
        )

    def overlap_analysis(
        self, *, minimum_count: int | None = None, show_progress: bool = False
    ) -> OverlapResults:
        """Get overlap analysis results."""
        return overlap_analysis(
            self.configuration,
            self.terms_exact,
            minimum_count=minimum_count,
            processed_mappings=self.processed_mappings,
            raw_mappings=self.raw_mappings,
            terms_observed=self.terms_observed,
            show_progress=show_progress,
        )

    def landscape_analysis(self, overlap_results: OverlapResults) -> LandscapeResult:
        """Get landscape analysis results."""
        return landscape_analysis(
            configuration=self.configuration,
            processed_mappings=overlap_results.processed_mappings,
            priority=overlap_results.processed_counts_df.index,
            terms_exact=self.terms_exact,
            terms_observed=self.terms_observed,
        )


@dataclass
class OverlapResults:
    """Results from mapping analysis."""

    raw_mappings: list[Mapping]
    raw_counts_df: pd.DataFrame
    processed_mappings: list[Mapping]
    counts: SymmetricCounter
    processed_counts_df: pd.DataFrame
    gains_df: pd.DataFrame
    percent_gains_df: pd.DataFrame
    minimum_count: int | None = None
    counts_drawing: bytes = field(init=False)

    def __post_init__(self) -> None:
        """Initialize the object by creating a drawing of the counter."""
        if self.minimum_count is None:
            self.minimum_count = 20
        self.counts_drawing = draw_counter(
            self.counts, cls=nx.Graph, minimum_count=self.minimum_count
        )

    def write(self, directory: str | Path) -> None:
        """Write the tables and charts to a directory."""
        directory = Path(directory).resolve()
        self.processed_counts_df.to_csv(directory / "counts.tsv", sep="\t", index=True)
        self.raw_counts_df.to_csv(directory / "raw_counts.tsv", sep="\t", index=True)
        directory.joinpath("graph.svg").write_bytes(self.counts_drawing)


def overlap_analysis(
    configuration: Configuration,
    terms: PrefixIdentifierDict,
    *,
    terms_observed: PrefixIdentifierDict,
    processed_mappings: list[Mapping],
    raw_mappings: list[Mapping],
    minimum_count: int | None = None,
    show_progress: bool = True,
) -> OverlapResults:
    """Run overlap analysis."""
    if not configuration.raw_pickle_path:
        raise ValueError("No raw pickle path available")
    raw_index = get_directed_index(
        raw_mappings, show_progress=show_progress, predicates={EXACT_MATCH, DB_XREF}
    )
    _, raw_counts_df = get_symmetric_counts_df(
        raw_index, terms, priority=configuration.priority, terms_observed=terms_observed
    )

    processed_index = get_directed_index(
        processed_mappings, show_progress=show_progress, predicates={EXACT_MATCH, DB_XREF}
    )
    processed_counts, processed_counts_df = get_symmetric_counts_df(
        processed_index, terms, priority=configuration.priority, terms_observed=terms_observed
    )

    gains_df = processed_counts_df - raw_counts_df
    percent_gains_df = 100.0 * (processed_counts_df - raw_counts_df) / raw_counts_df

    return OverlapResults(
        raw_mappings=raw_mappings,
        raw_counts_df=raw_counts_df,
        processed_mappings=processed_mappings,
        counts=processed_counts,
        processed_counts_df=processed_counts_df,
        gains_df=gains_df,
        percent_gains_df=percent_gains_df,
        minimum_count=minimum_count,
    )


def get_summary_df(
    prefixes: list[str],
    *,
    subsets: SubsetConfiguration | None = None,
    terms_exact: PrefixIdentifierDict,
    terms_observed: PrefixIdentifierDict,
) -> pd.DataFrame:
    """Create a summary dataframe for the prefixes in a landscape analysis.

    :param prefixes: The list of prefixes
    :param subsets: The subset configuration
    :param terms_exact: The dictionary of prefix -> collection of identifiers from :mod:`pyobo`
    :param terms_observed:
        The dictionary of prefix -> collection of identifiers encountered in the mappings
        appearing in the landscape analysis. This should be calculated from raw mappings
        to make sure that it accounts for any that might be filtered out during processing.
    :return: A pandas dataframe with the following columns:

        1. Prefix
        2. Name
        3. License
        4. Version
        5. Terms - the number of terms in the resource. If the full term list can be looked up
           with :mod:`pyobo`, then this is considered as exact. Otherwise, this will be estimated
           based on the number of unique terms appearing in the mappings. This is typically an
           underestimate since not necessarily all terms appear in mappings.
        6. Exact. Will be "true" if :mod:`pyobo` supports looking up all terms from the resource.
           Otherwise, will be "false"
    """
    import bioversions

    summary_rows = []
    if subsets is None:
        subsets = {}
    for prefix in prefixes:
        exact, count = _count_terms(prefix, terms_exact, terms_observed)
        if not exact:
            status = "observed"
        elif prefix in subsets:
            status = "subset"
        else:
            status = "full"
        row = (
            prefix,
            bioregistry.get_name(prefix),
            bioregistry.get_license(prefix),
            bioversions.get_version(prefix, strict=False),
            count,
            status,
        )
        summary_rows.append(row)

    df = pd.DataFrame(
        summary_rows, columns=["prefix", "name", "license", "version", "terms", "status"]
    )
    df = df.set_index("prefix")
    return df


def get_symmetric_counts_df(
    directed: DirectedIndex,
    terms: PrefixIdentifierDict,
    priority: list[str],
    *,
    terms_observed: PrefixIdentifierDict,
) -> tuple[SymmetricCounter, pd.DataFrame]:
    """Create a symmetric mapping counts dataframe from a directed index."""
    counter = get_symmetric_counter(
        directed=directed, terms_exact=terms, priority=priority, terms_observed=terms_observed
    )
    df = counter_to_df(counter, priority=priority).fillna(0).astype(int)
    return counter, df


def draw_counter(
    counter: SymmetricCounter,
    scaling_factor: float = 3.0,
    count_format: str = ",",
    cls: type[nx.Graph] = nx.DiGraph,
    minimum_count: float = 0.0,
    prog: str = "dot",
    output_format: str = "svg",
    direction: str = "LR",
) -> bytes:
    """Draw a source/target prefix pair counter as a network."""
    graph = cls()
    renames = {}
    for (source_prefix, target_prefix), count in counter.items():
        if not count:
            continue
        if source_prefix == target_prefix:
            renames[source_prefix] = f"{source_prefix}\n{count:,}"
            continue
        if count <= minimum_count:
            continue
        graph.add_edge(source_prefix, target_prefix, label=f"{count:{count_format}}")

    # rename from prefix -> prefix + count
    graph = nx.relabel_nodes(graph, renames)

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
    return cast(bytes, agraph.draw(prog=prog, format=output_format))


def counter_to_df(
    counter: SymmetricCounter, priority: list[str], drop_missing: bool = True
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


def count_unobserved(
    *,
    prefixes: t.Collection[str],
    terms_exact: PrefixIdentifierDict,
    terms_observed: PrefixIdentifierDict,
) -> t.Counter[frozenset[str]]:
    """Count the number of unobserved entities for each prefix."""
    rv: t.Counter[frozenset[str]] = Counter()
    for prefix in prefixes:
        observed_identifiers = terms_observed.get(prefix)
        if not observed_identifiers:
            # This situation doesn't really make sense - if the prefix is in the given list, and
            # it doesn't appear at all in the mappings, don't count it
            continue
        identifiers = terms_exact.get(prefix)
        if not identifiers:
            # The term list for the resource corresponding to the prefix is unavailable.
            # There might still be observed terms for this prefix, but they are all appearing
            # in mappings. Therefore, the count for this resource is zero, since all entities
            # are observed in mappings
            count = 0
        else:
            # Get the terms appearing in mappings for this vocabulary, then get the difference
            # between the whole term list and the ones appearing in mappings to count how
            # many are unique to the specific resource represented by the prefix
            unmapped_terms = set(identifiers).difference(observed_identifiers)
            count = len(unmapped_terms)
        rv[frozenset([prefix])] = count
    return rv


def landscape_analysis(
    configuration: Configuration,
    processed_mappings: list[Mapping],
    terms_exact: PrefixIdentifierDict,
    priority: list[str],
    *,
    terms_observed: PrefixIdentifierDict,
) -> LandscapeResult:
    """Run the landscape analysis."""
    mapped_counter = count_component_sizes(mappings=processed_mappings, prefix_allowlist=priority)

    #: A count of the number of entities that have at least mapping.
    #: This is calculated by the appearance of a weakly connected component
    #: in :func:`_get_counter`. This needs to be calculated before enriching
    #: the resulting counter object with entities that don't appear in mappings
    at_least_1_mapping = sum(mapped_counter.values())

    #: A count of the number of entities appearing in _all_ resources.
    #: Also calculated the same way with :func:`_get_counter`
    conserved = mapped_counter[frozenset(priority)]

    single_counter = count_unobserved(
        prefixes=priority,
        terms_exact=terms_exact,
        terms_observed=terms_observed,
    )

    #: A count of the number of entities that have no mappings.
    #: This is calculated based on the set difference between entities
    #: appearing in mappings and the preloaded terms lists
    only_1_mapping = sum(single_counter.values())

    counter = mapped_counter + single_counter

    total_entity_estimate = sum(counter.values())

    total_terms = sum(
        _count_terms(prefix, terms_exact, terms_observed).count for prefix in configuration.priority
    )

    return LandscapeResult(
        configuration=configuration,
        at_least_1_mapping=at_least_1_mapping,
        only_1_mapping=only_1_mapping,
        reduced_term_count=total_entity_estimate,
        total_term_count=total_terms,
        conserved=conserved,
        priority=priority,
        mapped_counter=mapped_counter,
        single_counter=single_counter,
    )


@dataclass
class LandscapeResult:
    """Describes results of landscape analysis."""

    configuration: Configuration
    priority: list[str]
    at_least_1_mapping: int
    only_1_mapping: int
    conserved: int
    reduced_term_count: int
    total_term_count: int
    mapped_counter: t.Counter[frozenset[str]]
    single_counter: t.Counter[frozenset[str]]
    counter: t.Counter[frozenset[str]] = field(init=False)
    distribution: t.Counter[int] = field(init=False)

    def __post_init__(self) -> None:
        """Post initialize the landscape result object."""
        self.counter = self.mapped_counter + self.single_counter
        self.distribution = self.get_distribution()

    def reduction_percent(self) -> float:
        """Get the reduction percent."""
        return (self.total_term_count - self.reduced_term_count) / self.total_term_count

    def get_description_markdown(self) -> str:
        """Describe the results in English prose."""
        return f"""\
            This estimates a total of {self.reduced_term_count:,} unique entities.

            - {self.at_least_1_mapping:,}
              ({self.at_least_1_mapping / self.reduced_term_count:.1%}) have
              at least one mapping.
            - {self.only_1_mapping:,} ({self.only_1_mapping / self.reduced_term_count:.1%})
              are unique to a single resource.
            - {self.conserved:,} ({self.conserved / self.reduced_term_count:.1%})
              appear in all {len(self.priority)} resources.

            This estimate is susceptible to several caveats:

            - Missing mappings inflates this measurement
            - Generic resources like MeSH contain irrelevant entities that can't be mapped
        """

    def get_reduction_text(self, configuration: Configuration) -> str:
        """Get text summarizing the efficacy of reduction."""
        return dedent(
            rf"""\
            The landscape of {len(configuration.priority)} resources has {self.total_term_count:,} total terms.
            After merging redundant nodes based on mappings, inference, and reasoning, there
            are {self.reduced_term_count:,} unique concepts. Using the reduction formula
            $\frac{{\text{{total terms}} - \text{{reduced terms}}}}{{\text{{total terms}}}}$,
            this is a {self.reduction_percent:.1%} reduction.
            """
        )

    def get_upset_df(self) -> pd.DataFrame:
        """Get an :mod:`upsetplot`-compatible dataframe for the result counter."""
        import upsetplot

        return upsetplot.from_memberships(*zip(*self.counter.most_common(), strict=False))

    def plot_upset(self) -> None:
        """Plot the results with an UpSet plot."""
        upset_df = self.get_upset_df()
        """Here's what the output from upsetplot.plot looks like:

        {'matrix': <Axes: >,
         'shading': <Axes: >,
         'totals': <Axes: >,
         'intersections': <Axes: ylabel='Intersection size'>}
        """
        import upsetplot

        plot_result = upsetplot.plot(
            upset_df,
            # show_counts=True,
        )
        plot_result["intersections"].set_yscale("log")
        plot_result["intersections"].set_ylim([1, plot_result["intersections"].get_ylim()[1]])
        # plot_result["totals"].set_xlabel("Size")
        mm, _ = plot_result["totals"].get_xlim()
        plot_result["totals"].set_xlim([mm, 1])
        plot_result["totals"].set_xscale("log")  # gets domain error

    def get_distribution(self) -> t.Counter[int]:
        """Get the distribution of component sizes."""
        counter: t.Counter[int] = Counter()
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
        width_ratio: float = 0.7,
        top_ratio: float = 20.0,
    ) -> None:
        """Plot the distribution of component sizes."""
        import seaborn as sns
        from matplotlib import pyplot as plt

        fig, ax = plt.subplots(figsize=(1 + len(self.distribution) * width_ratio, height))
        sns.barplot(self.distribution, ax=ax)

        for index, value in self.distribution.items():
            if value == 0:
                # don't bother writing labels for zero
                continue
            plt.text(
                index - 1,
                value + 0.2,
                f"{value:,}\n({value / self.reduced_term_count:.1%})",
                ha="center",
                va="bottom",
            )

        ax.set_xlabel(f"# {self.configuration.key.title()} Resources a Concept Appears in")
        ax.set_ylabel("Count")
        ax.set_title(
            f"{self.configuration.key.title()} Landscape of {self.reduced_term_count:,} Unique Concepts"
        )
        ax.set_yscale("log")
        # since we're in a log scale, pad half of the max value to the top to make sure
        # the counts fit in the box
        a, b = ax.get_ylim()
        ax.set_ylim((a, b + top_ratio * max(self.distribution.values())))
