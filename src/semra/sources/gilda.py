"""Get MeSH mappings from Gilda."""

from __future__ import annotations

from pathlib import Path

import bioregistry
import pandas as pd
import sssom_pydantic
from pydantic import AnyUrl
from pyobo import Reference
from sssom_pydantic import SemanticMapping
from tqdm.auto import tqdm

from semra.constants import CC0_URL
from semra.vocabulary import EXACT_MATCH, LEXICAL_MAPPING

__all__ = [
    "get_gilda_mappings",
]

GILDA_LOCAL = Path("/Users/cthoyt/dev/gilda/gilda/resources/mesh_mappings.tsv")
GILDA_MAPPINGS_URL = (
    "https://raw.githubusercontent.com/indralab/gilda/master/gilda/resources/mesh_mappings.tsv"
)
GILDA_MAPPINGS_URL_PYDANTIC = AnyUrl(GILDA_MAPPINGS_URL)
SOURCE = Reference(prefix="wikidata", identifier="Q120549845", name="Gilda")
GILDA_METADATA = sssom_pydantic.MappingSet(id=GILDA_MAPPINGS_URL_PYDANTIC)


def get_gilda_mappings(*, confidence: float = 0.95) -> list[SemanticMapping]:
    """Get MeSH and potentially other mappings from Gilda."""
    df = pd.read_csv(
        GILDA_MAPPINGS_URL if not GILDA_LOCAL.is_file() else GILDA_LOCAL,
        sep="\t",
        header=None,
        usecols=[0, 1, 3, 4],
        names=["source_prefix", "source_id", "target_prefix", "target_id"],
    )
    for k in ("source_prefix", "target_prefix"):
        df[k] = df[k].map(bioregistry.normalize_prefix)
    rv = []
    for sp, si, tp, ti in tqdm(
        df.values, desc="Loading Gilda", unit="mapping", unit_scale=True, leave=False
    ):
        if not sp or not tp:
            continue
        m = SemanticMapping(
            subject=Reference(prefix=sp, identifier=si),
            predicate=EXACT_MATCH,
            object=Reference(prefix=tp, identifier=ti),
            justification=LEXICAL_MAPPING,
            confidence=confidence,
            license=CC0_URL,
            source=SOURCE,
            provider=GILDA_MAPPINGS_URL_PYDANTIC,
        )
        rv.append(m)
    return rv


if __name__ == "__main__":
    get_gilda_mappings()
