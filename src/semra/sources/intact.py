"""Get mappings from IntAct."""

from __future__ import annotations

import bioregistry
import bioversions
import pandas as pd
from pydantic import ValidationError
from pyobo import Reference
from tqdm import tqdm

from semra.rules import EXACT_MATCH, UNSPECIFIED_MAPPING
from semra.struct import Mapping, MappingSet, SimpleEvidence

__all__ = [
    "get_intact_complexportal_mappings",
    "get_intact_reactome_mappings",
]

COMPLEXPORTAL_MAPPINGS_UNVERSIONED = (
    "ftp://ftp.ebi.ac.uk/pub/databases/intact/complex/current/various/cpx_ebi_ac_translation.txt"
)
REACTOME_MAPPINGS_UNVERSIONED = (
    "ftp://ftp.ebi.ac.uk/pub/databases/intact/current/various/reactome.dat"
)
INTACT_CONFIDENCE = 0.99


def _get_mappings(url: str, target_prefix: str) -> list[Mapping]:
    try:
        v = bioversions.get_version("intact")
    except ValueError:
        v = None
    license = bioregistry.get_license("intact")
    df = pd.read_csv(url, sep="\t", header=None, usecols=[0, 1])
    evidence = SimpleEvidence(
        justification=UNSPECIFIED_MAPPING,
        mapping_set=MappingSet(
            name="intact", version=v, license=license, confidence=INTACT_CONFIDENCE
        ),
    )
    rv = []
    for intact_id, target_identifier in df.values:
        try:
            obj = Reference(prefix=target_prefix, identifier=target_identifier)
        except ValidationError:
            tqdm.write(f"[intact:{intact_id}] invalid xref: {target_prefix}:{target_identifier}")
            continue
        mapping = Mapping(
            subject=Reference(prefix="intact", identifier=intact_id),
            predicate=EXACT_MATCH,
            object=obj,
            evidence=[evidence],
        )
        rv.append(mapping)

    return rv


def get_intact_complexportal_mappings() -> list[Mapping]:
    """Get IntAct-Complex Portal xrefs."""
    return _get_mappings(COMPLEXPORTAL_MAPPINGS_UNVERSIONED, "complexportal")


def get_intact_reactome_mappings() -> list[Mapping]:
    """Get IntAct-Reactome xrefs."""
    return _get_mappings(REACTOME_MAPPINGS_UNVERSIONED, "reactome")
