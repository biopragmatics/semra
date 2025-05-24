"""Landscape analysis utilities."""

import json
import typing as t
import warnings
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from textwrap import dedent
from typing import cast

import bioregistry
import matplotlib.pyplot as plt
import networkx as nx
import pandas as pd
import pyobo
import seaborn as sns
import upsetplot
from IPython.display import SVG, Markdown, display
from matplotlib_inline.backend_inline import set_matplotlib_formats
from pyobo.sources.mesh import get_mesh_category_curies

from semra import Reference
from semra.api import (
    count_component_sizes,
    filter_subsets,
    get_index,
    hydrate_subsets,
)
from semra.pipeline import Configuration, SubsetConfiguration
from semra.rules import DB_XREF, EXACT_MATCH
from semra.struct import Mapping

__all__ = [
    "counter_to_df",
    "draw_counter",
    "get_mesh_category_curies",
    "get_symmetric_counts_df",
    "landscape_analysis",
    "notebook",
    "overlap_analysis",
]


DirectedIndex = dict[tuple[str, str], set[str]]
XXCounter = t.Counter[tuple[str, str]]
XXTerms = t.Mapping[str, t.Mapping[str, str]]
XXObservedTerms = dict[str, set[str]]
XXSubsets = t.Mapping[str, t.Collection[str]]


def _markdown(x: str) -> None:
    display(Markdown(dedent(x)))


def notebook(
    configuration: Configuration,
    *,
    output_directory: str | Path | None = None,
    matplotlib_formats: str | None = "svg",
    show: bool = True,
    minimum_count: int | None = None,
    show_progress: bool = False,
) -> tuple["OverlapResults", "LandscapeResult"]:
    """Run the landscape analysis inside a Jupyter notebook."""
    if not configuration.raw_pickle_path:
        raise ValueError
    if matplotlib_formats:
        set_matplotlib_formats(matplotlib_formats)
    if output_directory is None:
        output_directory = configuration.raw_pickle_path.parent
    output_directory = Path(output_directory).expanduser().resolve()
    configuration_path = output_directory.joinpath("configuration.json")
    configuration_path.write_text(
        configuration.model_dump_json(indent=2, exclude_none=True, exclude_unset=True)
    )

    terms = get_terms(configuration.priority, configuration.subsets, show_progress=show_progress)

    hydrated_subsets = configuration.get_hydrated_subsets(show_progress=show_progress)

    raw_mappings = configuration.read_raw_mappings()
    if configuration.subsets:
        raw_mappings = filter_subsets(raw_mappings, hydrated_subsets)

    processed_mappings = configuration.read_processed_mappings()
    if configuration.subsets:
        processed_mappings = filter_subsets(processed_mappings, hydrated_subsets)

    terms_observed = get_observed_terms(processed_mappings)
    summary_df = get_summary_df(
        prefixes=configuration.priority,
        subsets=configuration.subsets,
        terms=terms,
        terms_observed=terms_observed,
    )
    summary_df.to_csv(output_directory.joinpath("summary.tsv"), sep="\t")
    number_pyobo_unavailable = (summary_df["terms"] == 0).sum()
    _markdown(
        """\
    ## Summarize the Resources

    We summarize the resources used in the landscape analysis, including their
    [Bioregistry](https://bioregistry.io) prefix, license, current version, and
    number of terms (i.e., named concepts) they contain.
    """
    )
    if number_pyobo_unavailable > 0:
        _markdown(
            f"""\
        {number_pyobo_unavailable} resources were not available through
        [PyOBO](https://github.com/biopragmatics/pyobo). Therefore, we estimate the number
        of terms in that resource based on the ones appearing in mappings. Note that these
        are typically an underestimate.
        """
        )

    display(summary_df)

    _summary_total = summary_df["terms"].sum()
    _markdown(
        f"There are a total of {_summary_total:,} terms across the {len(summary_df.index):,} "
        f"resources."
    )

    _markdown(
        """\
    ## Summarize the Mappings

    In order to summarize the mappings, we're going to load them, index them, and count
    the number of mappings between each pair of resources. The self-mapping column is
    the count of terms in the resource. We'll do this to the raw mappings first, then
    to the processed mappings, then compare them.
    """
    )
    overlap_results = overlap_analysis(
        configuration,
        terms,
        minimum_count=minimum_count,
        processed_mappings=processed_mappings,
        raw_mappings=raw_mappings,
        terms_observed=terms_observed,
        show_progress=show_progress,
    )
    overlap_results.write(output_directory)
    _markdown(
        "First, we summarize the raw mappings, i.e., the mappings that are directly available "
        "from the sources"
    )
    display(overlap_results.raw_counts_df)
    _markdown(
        "Next, we summarize the processed mappings, which include inference, reasoning, and "
        "confidence filtering."
    )
    display(overlap_results.processed_counts_df)
    _markdown("Below is an graph-based view on the processed mappings.")
    display(SVG(overlap_results.counts_drawing))
    _markdown(
        """\
    ## Comparison

    The following comparison shows the absolute number of mappings added by processing/inference.
    Across the board, this process adds large numbers of mappings to most resources, especially
    ones that were previously only connected to a small number of other resources.
    """
    )
    display(overlap_results.gains_df)
    _markdown(
        """\
    Here's an alternative view on the number of mappings normalized to show percentage gain.

    Note:

    - `inf` means that there were no mappings before and now there are a non-zero number of
       mappings
    - `NaN` means there were no mappings before inference and continue to be no mappings after
       inference
    """
    )
    display(overlap_results.percent_gains_df.round(1))
    _markdown(
        """\
        ## Landscape Analysis

        Before, we looked at the overlaps between each resource. Now, we use that information
        jointly to estimate the number of terms in the landscape itself, and estimate how much
        of the landscape each resource covers.
    """
    )

    # note we're using the sliced counts dataframe index instead of the
    # original priority since we threw a couple prefixes away along the way
    landscape_results = landscape_analysis(
        configuration=configuration,
        processed_mappings=overlap_results.processed_mappings,
        prefix_to_identifiers=terms,
        priority=overlap_results.processed_counts_df.index,
        prefix_to_observed_identifiers=terms_observed,
    )

    _markdown(landscape_results.get_description_markdown())

    n_prefixes = len(overlap_results.processed_counts_df.index)
    number_overlaps = 2**n_prefixes - 1
    _markdown(
        f"""\
    Because there are {n_prefixes} prefixes, there are {number_overlaps:,} possible overlaps to consider.
    Therefore, a Venn diagram is not possible, so we
    we use an [UpSet plot](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC4720993)
    (Lex *et al.*, 2014) as a high-dimensional Venn diagram.
    """
    )
    with warnings.catch_warnings():
        warnings.simplefilter(action="ignore", category=FutureWarning)
        # we have to wrap the upset plot functionality with the future
        # warning catching because it uses deprecated matplotlib and
        # pandas functionality. unfortunataely, it appears the upstream
        # https://github.com/jnothman/UpSetPlot is inactive
        landscape_results.plot_upset()
    plt.savefig(output_directory.joinpath("landscape_upset.svg"))
    if show:
        plt.show()

    _markdown(
        """\
        We now aggregate the mappings together to estimate the number of unique entities and number
        that appear in each group of resources.
        """
    )
    landscape_results.plot_distribution()
    plt.tight_layout()
    plt.savefig(output_directory.joinpath("landscape_histogram.svg"))
    if show:
        plt.show()

    reduced = landscape_results.total_entity_estimate
    total_terms = 0
    for prefix in configuration.priority:
        count, _exact = _count_terms(prefix, terms=terms, terms_observed=terms_observed)
        total_terms += count
    reduction_percent = (total_terms - reduced) / total_terms
    _markdown(
        rf"""\
        The landscape of {len(configuration.priority)} resources has {total_terms:,} total terms.
        After merging redundant nodes based on mappings, inference, and reasoning, there
        are {reduced:,} unique concepts. Using the reduction formula
        $\frac{{\text{{total terms}} - \text{{reduced terms}}}}{{\text{{total terms}}}}$,
        this is a {reduction_percent:.1%} reduction.
        """
    )
    _markdown(
        """\
    This is only an estimate and is susceptible to a few things:

    1. It can be artificially high because there are entities that _should_ be mapped, but are not
    2. It can be artificially low because there are entities that are incorrectly mapped, e.g., as
       a result of inference. The frontend curation interface can help identify and remove these
    3. It can be artificially low because for some vocabularies like SNOMED-CT, it's not possible
       to load a terms list, and therefore it's not possible to account for terms that aren't
       mapped. Therefore, we make a lower bound estimate based on the terms that appear in
       mappings.
    4. It can be artificially high if a vocabulary is used that covers many domains and is not
       properly subset'd. For example, EFO covers many different domains, so when doing disease
       landscape analysis, it should be subset to only terms in the disease hierarchy
       (i.e., appearing under ``efo:0000408``).
    5. It can be affected by terminology issues, such as the confusion between Orphanet and ORDO
    6. It can be affected by the existence of many-to-many mappings, which are filtered out during
       processing, which makes the estimate artificially high since some subset of those entities
       could be mapped, but it's not clear which should.
    """
    )

    stats = {
        "raw_term_count": total_terms,
        "unique_term_count": reduced,
        "reduction": reduction_percent,
        "distribution": landscape_results.distribution,
    }
    stats_path = output_directory.joinpath("stats.json")
    stats_path.write_text(json.dumps(stats, indent=2, sort_keys=True))

    return overlap_results, landscape_results


@dataclass
class OverlapResults:
    """Results from mapping analysis."""

    raw_mappings: list[Mapping]
    raw_counts_df: pd.DataFrame
    processed_mappings: list[Mapping]
    counts: XXCounter
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
    terms: XXTerms,
    *,
    terms_observed: XXObservedTerms,
    processed_mappings: list[Mapping],
    raw_mappings: list[Mapping],
    minimum_count: int | None = None,
    show_progress: bool = True,
) -> OverlapResults:
    """Run overlap analysis."""
    if not configuration.raw_pickle_path:
        raise ValueError("No raw pickle path available")
    raw_index = _get_summary_index(raw_mappings, show_progress=show_progress)
    _, raw_counts_df = get_symmetric_counts_df(
        raw_index, terms, priority=configuration.priority, terms_observed=terms_observed
    )

    processed_index = _get_summary_index(processed_mappings, show_progress=show_progress)
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


def get_terms(
    prefixes: list[str],
    subset_configuration: SubsetConfiguration | None = None,
    *,
    show_progress: bool = True,
) -> XXTerms:
    """Get the set of identifiers for each of the resources."""
    prefix_to_identifier_to_name = {}
    if subset_configuration is None:
        hydrated_subset_configuration: SubsetConfiguration = {}
    else:
        hydrated_subset_configuration = hydrate_subsets(
            subset_configuration, show_progress=show_progress
        )
    for prefix in prefixes:
        # TODO need to exclude default references here
        id_to_name = pyobo.get_id_name_mapping(prefix, use_tqdm=show_progress)
        subset: set[Reference] = set(hydrated_subset_configuration.get(prefix) or [])
        if subset:
            prefix_to_identifier_to_name[prefix] = {
                identifier: name
                for identifier, name in id_to_name.items()
                if _keep_in_subset(prefix=prefix, identifier=identifier, subset=subset)
            }
        else:
            prefix_to_identifier_to_name[prefix] = id_to_name
    return prefix_to_identifier_to_name


def _keep_in_subset(prefix: str, identifier: str, subset: set[Reference]) -> bool:
    # check if the identifier is a "default" reference
    if identifier.startswith(f"{prefix}#"):
        return False
    return Reference(prefix=prefix, identifier=identifier) in subset


def _count_terms(prefix: str, terms: XXTerms, terms_observed: XXObservedTerms) -> tuple[int, bool]:
    terms_exact = terms.get(prefix)
    if terms_exact:
        exact = True
        count = len(terms_exact)
    elif prefix in terms_observed:
        exact = False
        count = len(terms_observed[prefix])
    else:
        exact = False
        count = 0
    return count, exact


def get_summary_df(
    prefixes: list[str],
    *,
    subsets: SubsetConfiguration | None = None,
    terms: XXTerms,
    terms_observed: XXObservedTerms,
) -> pd.DataFrame:
    """Create a summary dataframe for the prefixes in a landscape analysis.

    :param prefixes: The list of prefixes
    :param subsets: The subset configuration
    :param terms: The dictionary of prefix -> collection of identifiers from :mod:`pyobo`
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
        count, exact = _count_terms(prefix, terms, terms_observed)
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


def _get_summary_index(
    mappings: t.Iterable[Mapping], *, show_progress: bool = True
) -> DirectedIndex:
    """Index which entities in each vocabulary have been mapped.

    :param mappings: An iterable of mappings to be indexed
    :return: A directed index

    For example, if we have the triple P1:1 skos:exactMatch P2:A and P1:1 skos:exactMatch P3:X, we
    would have the following index:

    .. code-block::

        {
           ("P1", "P2"): {"1"},
           ("P2", "P1"): {"A"},
           ("P1", "P3"): {"1"},
           ("P3", "P1"): {"X"},
        }
    """
    index = get_index(mappings, progress=show_progress, leave=False)
    directed: defaultdict[tuple[str, str], set[str]] = defaultdict(set)
    target_predicates = {EXACT_MATCH, DB_XREF}
    for triple in index:
        if triple.predicate in target_predicates:
            directed[triple.subject.prefix, triple.object.prefix].add(triple.subject.identifier)
            directed[triple.object.prefix, triple.subject.prefix].add(triple.object.identifier)
    return dict(directed)


def get_symmetric_counts_df(
    directed: DirectedIndex,
    terms: XXTerms,
    priority: list[str],
    *,
    terms_observed: XXObservedTerms,
) -> tuple[XXCounter, pd.DataFrame]:
    """Create a symmetric mapping counts dataframe from a directed index."""
    counter: XXCounter = Counter()

    for left_prefix, right_prefix in directed:
        left_observed_terms = directed[left_prefix, right_prefix]
        left_all_terms: t.Collection[str] = terms.get(left_prefix, [])
        if left_all_terms:
            left_observed_terms.intersection_update(left_all_terms)

        right_observed_terms = directed[right_prefix, left_prefix]
        right_all_terms: t.Collection[str] = terms.get(right_prefix, [])
        if right_all_terms:
            right_observed_terms.intersection_update(right_all_terms)

        counter[left_prefix, right_prefix] = max(
            len(left_observed_terms), len(right_observed_terms)
        )

    for prefix in priority:
        count, _exact = _count_terms(prefix, terms, terms_observed)
        counter[prefix, prefix] = count

    df = counter_to_df(counter, priority=priority).fillna(0).astype(int)
    return counter, df


def draw_counter(
    counter: XXCounter,
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
    counter: XXCounter, priority: list[str], drop_missing: bool = True
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


def get_observed_terms(mappings: t.Iterable[Mapping]) -> dict[str, set[str]]:
    """Get the set of terms appearing in each prefix."""
    entities: defaultdict[str, set[str]] = defaultdict(set)
    for mapping in mappings:
        for reference in (mapping.subject, mapping.object):
            entities[reference.prefix].add(reference.identifier)
    return dict(entities)


def count_unobserved(
    *,
    prefixes: t.Collection[str],
    prefix_to_identifiers: XXTerms,
    prefix_to_observed_identifiers: XXObservedTerms,
) -> t.Counter[frozenset[str]]:
    """Count the number of unobserved entities for each prefix."""
    rv: t.Counter[frozenset[str]] = Counter()
    for prefix in prefixes:
        observed_identifiers = prefix_to_observed_identifiers.get(prefix)
        if not observed_identifiers:
            # This situation doesn't really make sense - if the prefix is in the given list, and
            # it doesn't appear at all in the mappings, don't count it
            continue
        identifiers = prefix_to_identifiers.get(prefix)
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
    prefix_to_identifiers: XXTerms,
    priority: list[str],
    *,
    prefix_to_observed_identifiers: XXObservedTerms,
) -> "LandscapeResult":
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
        prefix_to_identifiers=prefix_to_identifiers,
        prefix_to_observed_identifiers=prefix_to_observed_identifiers,
    )

    #: A count of the number of entities that have no mappings.
    #: This is calculated based on the set difference between entities
    #: appearing in mappings and the preloaded terms lists
    only_1_mapping = sum(single_counter.values())

    counter = mapped_counter + single_counter

    total_entity_estimate = sum(counter.values())

    return LandscapeResult(
        configuration=configuration,
        at_least_1_mapping=at_least_1_mapping,
        only_1_mapping=only_1_mapping,
        total_entity_estimate=total_entity_estimate,
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
    total_entity_estimate: int
    mapped_counter: t.Counter[frozenset[str]]
    single_counter: t.Counter[frozenset[str]]
    counter: t.Counter[frozenset[str]] = field(init=False)
    distribution: t.Counter[int] = field(init=False)

    def __post_init__(self) -> None:
        """Post initialize the landscape result object."""
        self.counter = self.mapped_counter + self.single_counter
        self.distribution = self.get_distribution()

    def get_description_markdown(self) -> str:
        """Describe the results in English prose."""
        return f"""\
            This estimates a total of {self.total_entity_estimate:,} unique entities.

            - {self.at_least_1_mapping:,}
              ({self.at_least_1_mapping / self.total_entity_estimate:.1%}) have
              at least one mapping.
            - {self.only_1_mapping:,} ({self.only_1_mapping / self.total_entity_estimate:.1%})
              are unique to a single resource.
            - {self.conserved:,} ({self.conserved / self.total_entity_estimate:.1%})
              appear in all {len(self.priority)} resources.

            This estimate is susceptible to several caveats:

            - Missing mappings inflates this measurement
            - Generic resources like MeSH contain irrelevant entities that can't be mapped
        """

    def get_upset_df(self) -> pd.DataFrame:
        """Get an :mod:`upsetplot`-compatible dataframe for the result counter."""
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
        fig, ax = plt.subplots(figsize=(1 + len(self.distribution) * width_ratio, height))
        sns.barplot(self.distribution, ax=ax)

        for index, value in self.distribution.items():
            if value == 0:
                # don't bother writing labels for zero
                continue
            plt.text(
                index - 1,
                value + 0.2,
                f"{value:,}\n({value / self.total_entity_estimate:.1%})",
                ha="center",
                va="bottom",
            )

        ax.set_xlabel(f"# {self.configuration.key.title()} Resources a Concept Appears in")
        ax.set_ylabel("Count")
        ax.set_title(
            f"{self.configuration.key.title()} Landscape of {self.total_entity_estimate:,} Unique Concepts"
        )
        ax.set_yscale("log")
        # since we're in a log scale, pad half of the max value to the top to make sure
        # the counts fit in the box
        a, b = ax.get_ylim()
        ax.set_ylim((a, b + top_ratio * max(self.distribution.values())))
