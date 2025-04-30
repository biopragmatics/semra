"""Get mappings from FamPlex."""

from __future__ import annotations

import logging

import bioregistry
import pandas as pd
from pyobo import Reference

from semra.api import validate_mappings
from semra.rules import BEN_ORCID, EXACT_MATCH, MANUAL_MAPPING
from semra.struct import Mapping, MappingSet, SimpleEvidence

__all__ = [
    "get_fplx_mappings",
]

logger = logging.getLogger(__name__)

URL = "https://raw.githubusercontent.com/sorgerlab/famplex/master/equivalences.csv"
MAPPING_SET = MappingSet(name="fplx", confidence=0.99, license="CC0")


def get_fplx_mappings() -> list[Mapping]:
    """Get xrefs from FamPlex."""
    df = pd.read_csv(URL, header=None, names=["target_prefix", "target_id", "source_id"], sep=",")
    df = df[df["target_prefix"] != "MEDSCAN"]
    rv = [
        Mapping(
            subject=Reference(prefix="fplx", identifier=source_id),
            predicate=EXACT_MATCH,
            object=Reference(
                prefix=bioregistry.normalize_prefix(target_prefix),
                identifier=bioregistry.standardize_identifier(target_prefix, target_id),
            ),
            evidence=[
                SimpleEvidence(
                    justification=MANUAL_MAPPING, mapping_set=MAPPING_SET, author=BEN_ORCID
                )
            ],
        )
        for target_prefix, target_id, source_id in df.values
        if (
            target_prefix not in {"BEL"}
            and not (target_prefix == "NXP" and target_id.startswith("FA:"))  # is this a problem?
        )
    ]
    validate_mappings(rv, progress=False)
    return rv


if __name__ == "__main__":
    get_fplx_mappings()
