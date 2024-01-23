"""Get mappings from FamPlex."""

from __future__ import annotations

import logging

import bioregistry
import pandas as pd
from curies import Reference

from semra.api import validate_mappings
from semra.rules import BEN_ORCID, EXACT_MATCH, MANUAL_MAPPING
from semra.struct import Mapping, MappingSet, SimpleEvidence

__all__ = [
    "get_famplex_mappings",
]

logger = logging.getLogger(__name__)

URL = "https://github.com/sorgerlab/famplex/raw/master/equivalences.csv"
MAPPING_SET = MappingSet(name="famplex", confidence=0.99, license="CC0")


def get_famplex_mappings() -> list[Mapping]:
    """Get xrefs from FamPlex."""
    df = pd.read_csv(URL, header=None, names=["target_prefix", "target_id", "source_id"], sep=",")
    df = df[df["target_prefix"] != "MEDSCAN"]
    rv = [
        Mapping(
            s=Reference(prefix="fplx", identifier=source_id),
            p=EXACT_MATCH,
            o=Reference(
                prefix=bioregistry.normalize_prefix(target_prefix),
                identifier=bioregistry.standardize_identifier(target_prefix, target_id),
            ),
            evidence=[SimpleEvidence(justification=MANUAL_MAPPING, mapping_set=MAPPING_SET, author=BEN_ORCID)],
        )
        for target_prefix, target_id, source_id in df.values
        if (
            target_prefix not in {"BEL"}
            and not (target_prefix == "NXP" and target_id.startswith("FA:"))  # is this a problem?
        )
    ]
    validate_mappings(rv)
    return rv


if __name__ == "__main__":
    get_famplex_mappings()
