"""Get mappings from Biomappings."""

from __future__ import annotations

from semra.io import from_sssom
from semra.struct import Mapping

__all__ = [
    "from_biomappings_negative",
    "from_biomappings_predicted",
    "get_biomappings_positive_mappings",
]


def get_biomappings_positive_mappings() -> list[Mapping]:
    """Get positive mappings from Biomappings."""
    try:
        import biomappings.resources
    except ImportError:
        return read_remote_tsv("positive.sssom.tsv")
    else:
        return from_sssom(
            biomappings.resources.POSITIVES_SSSOM_PATH,
            mapping_set_title="Biomappings",
        )


def from_biomappings_negative() -> list[Mapping]:
    """Get negative mappings from Biomappings."""
    try:
        import biomappings.resources
    except ImportError:
        return read_remote_tsv("negative.sssom.tsv")
    else:
        return from_sssom(
            biomappings.resources.NEGATIVES_SSSOM_PATH,
            mapping_set_title="Biomappings",
        )


def from_biomappings_predicted() -> list[Mapping]:
    """Get predicted mappings from Biomappings."""
    try:
        import biomappings.resources
    except ImportError:
        return read_remote_tsv("predictions.sssom.tsv")
    else:
        return from_sssom(
            biomappings.resources.PREDICTIONS_SSSOM_PATH,
            mapping_set_title="Biomappings",
        )


BASE_URL = "https://github.com/biopragmatics/biomappings/raw/master/src/biomappings/resources"


def read_remote_tsv(name: str) -> list[Mapping]:
    """Load a remote mapping file from the Biomappings GitHub repository."""
    return from_sssom(f"{BASE_URL}/{name}")
