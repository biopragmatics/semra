"""Get mappings from Biomappings."""

from __future__ import annotations

from typing import Any

from semra.io import from_sssom
from semra.struct import Mapping

__all__ = [
    "from_biomappings_negative",
    "from_biomappings_predicted",
    "get_biomappings_positive_mappings",
]

_NAME = "Biomappings"


def get_biomappings_positive_mappings(*, remote_only: bool = False) -> list[Mapping]:
    """Get positive mappings from Biomappings."""
    if remote_only:
        return read_remote_tsv("positive.sssom.tsv", mapping_set_title=_NAME)

    try:
        from biomappings.utils import POSITIVES_SSSOM_PATH
    except ImportError:
        return read_remote_tsv(
            "positive.sssom.tsv",
            mapping_set_title=_NAME,
        )
    else:
        return from_sssom(POSITIVES_SSSOM_PATH, mapping_set_title=_NAME)


def from_biomappings_negative(*, remote_only: bool = False) -> list[Mapping]:
    """Get negative mappings from Biomappings."""
    if remote_only:
        return read_remote_tsv("negative.sssom.tsv", mapping_set_title=_NAME)

    try:
        from biomappings.utils import NEGATIVES_SSSOM_PATH
    except ImportError:
        return read_remote_tsv("negative.sssom.tsv", mapping_set_title=_NAME)
    else:
        return from_sssom(NEGATIVES_SSSOM_PATH, mapping_set_title=_NAME)


def from_biomappings_predicted(*, remote_only: bool = False) -> list[Mapping]:
    """Get predicted mappings from Biomappings."""
    if remote_only:
        return read_remote_tsv("predictions.sssom.tsv", mapping_set_title=_NAME)

    try:
        from biomappings.utils import PREDICTIONS_SSSOM_PATH
    except ImportError:
        return read_remote_tsv("predictions.sssom.tsv", mapping_set_title="Biomappings")
    else:
        return from_sssom(PREDICTIONS_SSSOM_PATH, mapping_set_title="Biomappings")


BASE_URL = "https://github.com/biopragmatics/biomappings/raw/master/src/biomappings/resources"


def read_remote_tsv(name: str, **kwargs: Any) -> list[Mapping]:
    """Load a remote mapping file from the Biomappings GitHub repository."""
    return from_sssom(f"{BASE_URL}/{name}", **kwargs)
