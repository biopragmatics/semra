"""Get MeSH mappings from Gilda."""

from __future__ import annotations

from pathlib import Path

import bioregistry
import pandas as pd
from pyobo import Reference
from tqdm.auto import tqdm

from semra.api import validate_mappings
from semra.rules import BEN_ORCID, EXACT_MATCH, LEXICAL_MAPPING
from semra.struct import Mapping, MappingSet, SimpleEvidence

__all__ = [
    "get_gilda_mappings",
]

GILDA_LOCAL = Path("/Users/cthoyt/dev/gilda/gilda/resources/mesh_mappings.tsv")
GILDA_MAPPINGS = (
    "https://raw.githubusercontent.com/indralab/gilda/master/gilda/resources/mesh_mappings.tsv"
)


def get_gilda_mappings(confidence: float = 0.95) -> list[Mapping]:
    """Get MeSH and potentially other mappings from Gilda."""
    df = pd.read_csv(
        GILDA_MAPPINGS if not GILDA_LOCAL.is_file() else GILDA_LOCAL,
        sep="\t",
        header=None,
        usecols=[0, 1, 3, 4],
        names=["source_prefix", "source_id", "target_prefix", "target_id"],
    )
    for k in ("source_prefix", "target_prefix"):
        df[k] = df[k].map(bioregistry.normalize_prefix)
    rv = []
    for sp, si, tp, ti in tqdm(df.values, desc="Loading Gilda", unit="mapping", unit_scale=True):
        if not sp or not tp:
            continue
        m = Mapping(
            subject=Reference(
                prefix=bioregistry.normalize_prefix(sp),
                identifier=bioregistry.standardize_identifier(sp, si),
            ),
            predicate=EXACT_MATCH,
            object=Reference(
                prefix=bioregistry.normalize_prefix(tp),
                identifier=bioregistry.standardize_identifier(tp, ti),
            ),
            evidence=[
                SimpleEvidence(
                    justification=LEXICAL_MAPPING,
                    mapping_set=MappingSet(name="gilda_mesh", confidence=confidence, license="CC0"),
                    author=BEN_ORCID,
                )
            ],
        )
        rv.append(m)
    validate_mappings(rv)
    return rv


if __name__ == "__main__":
    get_gilda_mappings()
