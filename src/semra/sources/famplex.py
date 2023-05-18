"""Get mappings from FamPlex."""

import logging

import bioregistry
import pandas as pd

from semra import EXACT_MATCH, Mapping, Reference, SimpleEvidence
from semra.rules import MANUAL_MAPPING

__all__ = [
    "get_famplex_mappings",
]

logger = logging.getLogger(__name__)

URL = "https://github.com/sorgerlab/famplex/raw/master/equivalences.csv"


def get_famplex_mappings() -> list[Mapping]:
    """Get xrefs from FamPlex."""
    df = pd.read_csv(URL, header=None, names=["target_prefix", "target_id", "source_id"], sep=",")
    df = df[df["target_prefix"] != "MEDSCAN"]
    return [
        Mapping(
            s=Reference(prefix="famplex", identifier=source_id),
            p=EXACT_MATCH,
            o=Reference(
                prefix=bioregistry.normalize_prefix(target_prefix),
                identifier=bioregistry.standardize_identifier(target_prefix, target_id),
            ),
            evidence=[SimpleEvidence(justification=MANUAL_MAPPING, mapping_set="famplex", confidence=0.99)],
        )
        for target_prefix, target_id, source_id in df.values
    ]
