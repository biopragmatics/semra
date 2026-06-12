"""Get mappings from FamPlex."""

from __future__ import annotations

import bioregistry
import pandas as pd
from pydantic import AnyUrl
from pyobo import Reference
from sssom_pydantic import SemanticMapping

from semra.vocabulary import BEN_REFERENCE, EXACT_MATCH, MANUAL_MAPPING

__all__ = [
    "get_fplx_mappings",
]

URL = "https://raw.githubusercontent.com/sorgerlab/famplex/master/equivalences.csv"


def get_fplx_mappings(*, confidence: float = 0.99) -> list[SemanticMapping]:
    """Get xrefs from FamPlex."""
    df = pd.read_csv(URL, header=None, names=["target_prefix", "target_id", "source_id"], sep=",")
    df = df[df["target_prefix"] != "MEDSCAN"]
    license_url = bioregistry.get_license_url("fplx")
    provider = AnyUrl(URL)
    rv = [
        SemanticMapping(
            subject=Reference(prefix="fplx", identifier=source_id),
            predicate=EXACT_MATCH,
            object=Reference(prefix=target_prefix, identifier=target_id),
            justification=MANUAL_MAPPING,
            authors=[BEN_REFERENCE],
            source=Reference(prefix="bioregistry", identifier="fplx"),
            provider=provider,
            confidence=confidence,
            license=license_url,
        )
        for target_prefix, target_id, source_id in df.values
        if (
            target_prefix not in {"BEL"}
            and not (target_prefix == "NXP" and target_id.startswith("FA:"))  # is this a problem?
        )
    ]
    return rv


if __name__ == "__main__":
    get_fplx_mappings()
