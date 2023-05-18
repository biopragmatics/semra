"""Get MeSH mappings from Gilda."""

from __future__ import annotations

from pathlib import Path

import bioregistry
import pandas as pd
from tqdm.auto import tqdm

from semra import EXACT_MATCH, Mapping, Reference, SimpleEvidence
from semra.rules import BEN_ORCID, LEXICAL_MAPPING

__all__ = [
    "from_gilda",
]

GILDA_LOCAL = Path("/Users/cthoyt/dev/gilda/gilda/resources/mesh_mappings.tsv")
GILDA_MAPPINGS = "https://raw.githubusercontent.com/indralab/gilda/master/gilda/resources/mesh_mappings.tsv"


def from_gilda(confidence: float = 0.95) -> list[Mapping]:
    """Get MeSH and potentially other mappings from Gilda."""
    df = pd.read_csv(
        GILDA_MAPPINGS if not GILDA_LOCAL.is_file() else GILDA_LOCAL,
        sep="\t",
        header=None,
        usecols=[0, 1, 3, 4],
        names=["source_prefix", "source_id", "target_prefix", "target_id"],
    )
    for k in ("source_prefix", "target_prefix"):
        df[k] = df[k].map(bioregistry.normalize_prefix)  # type:ignore
    rv = []
    for sp, si, tp, ti in tqdm(df.values, desc="Loading Gilda", unit="mapping", unit_scale=True):
        if not sp or not tp:
            continue
        m = Mapping(
            s=Reference(prefix=sp, identifier=bioregistry.standardize_identifier(sp, si)),
            p=EXACT_MATCH,
            o=Reference(prefix=tp, identifier=bioregistry.standardize_identifier(tp, ti)),
            evidence=[
                SimpleEvidence(
                    justification=LEXICAL_MAPPING,
                    mapping_set="gilda_mesh",
                    author=BEN_ORCID,
                    confidence=confidence,
                )
            ],
        )
        rv.append(m)
    return rv
