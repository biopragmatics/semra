"""Import ComPath mappings between pathways."""

from collections.abc import Iterable

import pandas as pd
from pydantic import AnyUrl
from pyobo import Reference
from pystow.utils import get_commit
from sssom_pydantic import SemanticMapping

from semra.constants import CC0_URL
from semra.vocabulary import EXACT_MATCH, MANUAL_MAPPING

__all__ = [
    "get_compath_mappings",
]


def _get_df(
    title: str, *, sha: str, sep: str = ",", confidence: float = 0.99
) -> list[SemanticMapping]:
    url = f"https://raw.githubusercontent.com/ComPath/compath-resources/{sha}/mappings/{title}"
    df = pd.read_csv(
        url,
        sep=sep,
        usecols=["Source Resource", "Source ID", "Mapping Type", "Target Resource", "Target ID"],
    )
    df = df[df["Mapping Type"] == "equivalentTo"]
    del df["Mapping Type"]
    provider = AnyUrl(url)
    source = Reference(prefix="wikidata", identifier="Q116908748")
    daniel = Reference(prefix="orcid", identifier="0000-0002-2046-6145")
    return [
        SemanticMapping(
            subject=Reference(prefix=s_p, identifier=_fix_kegg_identifier(s_p, s_i)),
            predicate=EXACT_MATCH,
            object=Reference(prefix=t_p, identifier=_fix_kegg_identifier(t_p, t_i)),
            justification=MANUAL_MAPPING,
            authors=[daniel],
            license=CC0_URL,
            confidence=confidence,
            source=source,
            provider=provider,
        )
        for s_p, s_i, t_p, t_i in df.values
    ]


def _fix_kegg_identifier(prefix: str, identifier: str) -> str:
    if prefix == "kegg.pathway":
        return identifier[len("path:") :]
    return identifier


def iter_compath_dfs() -> Iterable[SemanticMapping]:
    """Iterate over all ComPath mappings."""
    sha = get_commit("ComPath", "compath-resources")

    yield from _get_df("kegg_reactome.csv", sha=sha)
    yield from _get_df("kegg_wikipathways.csv", sha=sha)
    yield from _get_df("pathbank_kegg.csv", sha=sha)
    yield from _get_df("pathbank_reactome.csv", sha=sha)
    yield from _get_df("pathbank_wikipathways.csv", sha=sha)
    yield from _get_df("special_mappings.csv", sha=sha)
    yield from _get_df("wikipathways_reactome.csv", sha=sha)


def get_compath_mappings() -> list[SemanticMapping]:
    """Iterate over all ComPath mappings."""
    return list(iter_compath_dfs())
