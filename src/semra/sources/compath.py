"""Import ComPath mappings between pathways."""

from collections.abc import Iterable

import pandas as pd
from pyobo import Reference
from pystow.utils import get_commit

from semra.rules import EXACT_MATCH, MANUAL_MAPPING
from semra.struct import Mapping, MappingSet, SimpleEvidence

__all__ = [
    "get_compath_mappings",
]


def _get_df(name: str, *, sha: str, sep: str = ",") -> list[Mapping]:
    url = f"https://raw.githubusercontent.com/ComPath/compath-resources/{sha}/mappings/{name}"
    df = pd.read_csv(
        url,
        sep=sep,
        usecols=["Source Resource", "Source ID", "Mapping Type", "Target Resource", "Target ID"],
    )
    df = df[df["Mapping Type"] == "equivalentTo"]
    del df["Mapping Type"]

    return [
        Mapping(
            subject=Reference(prefix=s_p, identifier=_fix_kegg_identifier(s_p, s_i)),
            predicate=EXACT_MATCH,
            object=Reference(prefix=t_p, identifier=_fix_kegg_identifier(t_p, t_i)),
            evidence=[
                SimpleEvidence(
                    mapping_set=MappingSet(name=name, confidence=0.99),
                    justification=MANUAL_MAPPING,
                )
            ],
        )
        for s_p, s_i, t_p, t_i in df.values
    ]


def _fix_kegg_identifier(prefix: str, identifier: str) -> str:
    if prefix == "kegg.pathway":
        return identifier[len("path:") :]
    return identifier


def iter_compath_dfs() -> Iterable[Mapping]:
    """Iterate over all ComPath mappings."""
    sha = get_commit("ComPath", "compath-resources")

    yield from _get_df("kegg_reactome.csv", sha=sha)
    yield from _get_df("kegg_wikipathways.csv", sha=sha)
    yield from _get_df("pathbank_kegg.csv", sha=sha)
    yield from _get_df("pathbank_reactome.csv", sha=sha)
    yield from _get_df("pathbank_wikipathways.csv", sha=sha)
    yield from _get_df("special_mappings.csv", sha=sha)
    yield from _get_df("wikipathways_reactome.csv", sha=sha)


def get_compath_mappings() -> list[Mapping]:
    """Iterate over all ComPath mappings."""
    return list(iter_compath_dfs())
