"""Supports landscape analysis."""

from collections import defaultdict, Counter

import networkx as nx
import typing as t
import pandas as pd
from dataclasses import dataclass
from semra.api import to_multidigraph, get_index
from semra.struct import Mapping
from semra.rules import EXACT_MATCH
import upsetplot
import seaborn as sns
import matplotlib.pyplot as plt

__all__ = [
    "get_directed_index",
    "draw_counter",
    "counter_to_df",
    "landscape_analysis",
]


def get_directed_index(mappings: t.Iterable[Mapping]) -> t.Dict[t.Tuple[str, str], t.Set[str]]:
    index = get_index(mappings, progress=False)
    directed: t.DefaultDict[t.Tuple[str, str], t.Set[str]] = defaultdict(set)
    for s, p, o in index:
        if p != EXACT_MATCH:
            continue
        directed[s.prefix, o.prefix].add(s.identifier)
        directed[o.prefix, s.prefix].add(o.identifier)
    return dict(directed)


def draw_counter(
    counter: t.Counter[t.Tuple[str, str]],
    scaling_factor: float = 3.0,
    count_format=",",
    cls: t.Type[nx.Graph] = nx.DiGraph,
    minimum_count: float = 0.0,
    prog: str = "dot",
    output_format: str = "svg",
    direction: str = "LR",
) -> str:
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
    counter: t.Counter[t.Tuple[str, str]], priority: t.List[str], default: float = 1.0, drop_missing: bool = True
) -> pd.DataFrame:
    """Get a dataframe from a counter."""
    rows = [[counter.get((p1, p2), None) for p2 in priority] for p1 in priority]
    df = pd.DataFrame(rows, columns=priority, index=priority)
    if drop_missing:
        df = df.dropna(axis=1, how="all")
        df = df.dropna(axis=0, how="all")

    # for p in priority:
    #     df.loc[p, p] = default

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


def landscape_analysis(mappings: t.List[Mapping], terms, priority: t.List[str]):
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
