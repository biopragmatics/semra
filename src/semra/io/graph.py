"""Graph I/O for SeMRA."""

from __future__ import annotations

import typing as t
from collections import defaultdict

import networkx as nx

from semra.struct import Evidence, Mapping, Reference
from semra.utils import semra_tqdm

__all__ = [
    "DIGRAPH_DATA_KEY",
    "MULTIDIGRAPH_DATA_KEY",
    "from_digraph",
    "from_multidigraph",
    "to_digraph",
    "to_multidigraph",
]

#: The key inside the data dictionary for a SeMRA mapping graph
#: in :class:`networkx.DiGraph` that has the predicate->evidence dict
DIGRAPH_DATA_KEY = "data"

#: The key inside the data dictionary for a SeMRA mapping graph
#: in :class:`networkx.MultiDiGraph` that has the evidence list
MULTIDIGRAPH_DATA_KEY = "evidence"


def to_digraph(mappings: t.Iterable[Mapping]) -> nx.DiGraph:
    """Convert mappings into a simple directed graph data model.

    :param mappings: An iterable of mappings

    :returns: A directed graph in which the nodes are :class:`curies.Reference` objects.
        A dictionary of predicate to evidence lists is put under the
        :data:`DIGRAPH_DATA_KEY`.

    .. warning::

        This function makes two assumptions:

        1. The graph has already been assembled using :func:`assemble_evidences`
        2. That only one predicate is used in the graph. If you want to handle multiple
           prediates, see :func:`to_multidigraph`
    """
    graph = nx.DiGraph()
    edges: defaultdict[tuple[Reference, Reference], defaultdict[Reference, list[Evidence]]] = (
        defaultdict(lambda: defaultdict(list))
    )
    for mapping in mappings:
        edges[mapping.subject, mapping.object][mapping.predicate].extend(mapping.evidence)
    for (s, o), data in edges.items():
        graph.add_edge(s, o, **{DIGRAPH_DATA_KEY: data})
    return graph


def from_digraph(graph: nx.DiGraph) -> list[Mapping]:
    """Extract mappings from a simple directed graph data model."""
    return [mapping for s, o in graph.edges() for mapping in _from_digraph_edge(graph, s, o)]


def _from_digraph_edge(graph: nx.Graph, s: Reference, o: Reference) -> t.Iterable[Mapping]:
    data = graph[s][o]
    for p, evidence in data[DIGRAPH_DATA_KEY].items():
        yield Mapping(subject=s, predicate=p, object=o, evidence=evidence)


def to_multidigraph(mappings: t.Iterable[Mapping], *, progress: bool = False) -> nx.MultiDiGraph:
    """Convert mappings into a multi directed graph data model.

    :param mappings: An iterable of mappings
    :param progress: Should a progress bar be shown?

    :returns: A directed graph in which the nodes are :class:`curies.Reference` objects.
        The predicate is used as the edge key and the evidences are stored in a list
        under the :data:`MULTIDIGRAPH_DATA_KEY` in each edge data dictionary.

    .. warning::

        This function makes the following assumptions:

        1. The graph has already been assembled using :func:`assemble_evidences`
    """
    graph = nx.MultiDiGraph()
    for mapping in semra_tqdm(mappings, progress=progress):
        graph.add_edge(
            mapping.subject,
            mapping.object,
            key=mapping.predicate,
            **{MULTIDIGRAPH_DATA_KEY: mapping.evidence},
        )
    return graph


def from_multidigraph(graph: nx.MultiDiGraph) -> list[Mapping]:
    """Extract mappings from a multi-directed graph data model."""
    return [
        Mapping(subject=s, predicate=p, object=o, evidence=data[MULTIDIGRAPH_DATA_KEY])
        for s, o, p, data in graph.edges(keys=True, data=True)
    ]
