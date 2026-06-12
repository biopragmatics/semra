"""Cross references from cbms2019.

.. seealso::

    https://github.com/pantapps/cbms2019 and https://doi.org/10.1109/CBMS.2019.00044
"""

import pandas as pd
import sssom_pydantic
from pydantic import AnyUrl, ValidationError
from pyobo import Reference
from sssom_pydantic import SemanticMapping
from tqdm import tqdm

from semra.vocabulary import CHAIN_MAPPING, EXACT_MATCH, UNSPECIFIED_MAPPING

__all__ = [
    "get_cbms2019_mappings",
]

#: Columns: DOID, DO name, xref xb, xref ix
base_url = "https://raw.githubusercontent.com/pantapps/cbms2019/master"
DOID_TO_ALL_1_URL = f"{base_url}/mesh_icd10cm_via_do_not_mapped_umls.tsv"
#: Columns: SNOMEDCT_ID, SNOMEDCIT_NAME, ICD10CM_ID, ICD10CM_NAME, MESH_ID
ALL_TO_ALL_1_URL = f"{base_url}/mesh_icd10cm_via_snomedct_not_mapped_umls.tsv"
#: Columns: DOID, DO name, xref xb, xref ix
DOID_TO_ALL_2_URL = f"{base_url}/mesh_snomedct_via_do_not_mapped_umls.tsv"
#: Columns: SNOMEDCT_ID, SNOMEDCIT_NAME, ICD10CM_ID, ICD10CM_NAME, MESH_ID
ALL_TO_ALL_2_URL = f"{base_url}/mesh_snomedct_via_icd10cm_not_mapped_umls.tsv"

CONFIDENCE = 0.8
NSM = {
    "MESH": "mesh",
    "ICD10CM": "icd10cm",
    "SNOMEDCT_US_2016_03_01": "snomedct",
}
SOURCE = Reference(prefix="github", identifier="pantapps/cbms2019")


def _get_doid(url: str, confidence: float) -> list[SemanticMapping]:
    df = pd.read_csv(url, sep="\t", usecols=["DO_ID", "resource", "resource_ID"])
    rv = []
    provider = AnyUrl(url)
    for do_id, target_prefix, target_id in df.values:
        try:
            obj = Reference(prefix=NSM[target_prefix], identifier=target_id)
        except ValidationError:
            tqdm.write(f"[doid:{do_id}] failed to parse xref {target_prefix}:{target_id}")
            continue
        mapping = sssom_pydantic.SemanticMapping(
            subject=Reference(prefix="doid", identifier=do_id.removeprefix("DOID:")),
            predicate=EXACT_MATCH,
            object=obj,
            justification=CHAIN_MAPPING,
            confidence=confidence,
            source=SOURCE,
            provider=provider,
        )
        rv.append(mapping)

    return rv


def _get_mesh_to_icd_via_doid(confidence: float) -> list[SemanticMapping]:
    return _get_doid(DOID_TO_ALL_1_URL, confidence=confidence)


def _get_mesh_to_icd_via_snomedct(*, confidence: float) -> list[SemanticMapping]:
    df = pd.read_csv(ALL_TO_ALL_1_URL, sep="\t", usecols=["SNOMEDCT_ID", "ICD10CM_ID", "MESH_ID"])
    rows = []
    provider = AnyUrl(ALL_TO_ALL_1_URL)
    for snomedct_id, icd_id, mesh_id in df.values:
        snomed_ref = Reference(prefix="snomedct", identifier=str(int(snomedct_id)))
        mesh_ref = Reference(prefix="mesh", identifier=mesh_id)
        rows.append(
            SemanticMapping(
                subject=mesh_ref,
                predicate=EXACT_MATCH,
                object=snomed_ref,
                justification=UNSPECIFIED_MAPPING,
                provider=provider,
                confidence=confidence,
                source=SOURCE,
            )
        )

        try:
            icd_ref = Reference(prefix="icd", identifier=icd_id)
        except ValidationError:
            pass
            # tqdm.write(f"failed to parse ICD: {icd_id}")
        else:
            rows.append(
                SemanticMapping(
                    subject=mesh_ref,
                    predicate=EXACT_MATCH,
                    object=icd_ref,
                    justification=CHAIN_MAPPING,
                    confidence=confidence,
                    provider=provider,
                    source=SOURCE,
                )
            )
            rows.append(
                SemanticMapping(
                    subject=icd_ref,
                    predicate=EXACT_MATCH,
                    object=snomed_ref,
                    justification=UNSPECIFIED_MAPPING,
                    provider=provider,
                    confidence=confidence,
                    source=SOURCE,
                )
            )
    return rows


def _get_mesh_to_snomedct_via_doid(confidence: float) -> list[SemanticMapping]:
    return _get_doid(DOID_TO_ALL_2_URL, confidence=confidence)


def _get_mesh_to_snomedct_via_icd(*, confidence: float) -> list[SemanticMapping]:
    df = pd.read_csv(
        ALL_TO_ALL_2_URL,
        sep="\t",
        usecols=["SNOMEDCT_ID", "ICD10CM_ID", "MESH_ID"],
        dtype={"SNOMEDCT_ID": float},
    )
    provider = AnyUrl(ALL_TO_ALL_2_URL)
    rows = []
    for snomedct_id, icd_id, mesh_id in df.values:
        snomed_ref = Reference(prefix="snomedct", identifier=str(int(snomedct_id)))
        mesh_ref = Reference(prefix="mesh", identifier=mesh_id)
        rows.append(
            SemanticMapping(
                subject=mesh_ref,
                predicate=EXACT_MATCH,
                object=snomed_ref,
                justification=CHAIN_MAPPING,
                source=SOURCE,
                confidence=confidence,
                provider=provider,
            )
        )

        try:
            icd_ref = Reference(prefix="icd", identifier=icd_id)
        except ValidationError:
            # tqdm.write(f"failed to parse ICD {icd_id}")
            pass
        else:
            rows.append(
                SemanticMapping(
                    subject=mesh_ref,
                    predicate=EXACT_MATCH,
                    object=icd_ref,
                    justification=UNSPECIFIED_MAPPING,
                    source=SOURCE,
                    confidence=confidence,
                    provider=provider,
                )
            )
            rows.append(
                SemanticMapping(
                    subject=icd_ref,
                    predicate=EXACT_MATCH,
                    object=snomed_ref,
                    justification=UNSPECIFIED_MAPPING,
                    source=SOURCE,
                    confidence=confidence,
                    provider=provider,
                )
            )
    return rows


def get_cbms2019_mappings(confidence: float | None = None) -> list[SemanticMapping]:
    """Get all CBMS2019 xrefs."""
    if confidence is None:
        confidence = CONFIDENCE
    return [
        *_get_mesh_to_icd_via_doid(confidence=confidence),
        *_get_mesh_to_icd_via_snomedct(confidence=confidence),
        *_get_mesh_to_snomedct_via_doid(confidence=confidence),
        *_get_mesh_to_snomedct_via_icd(confidence=confidence),
    ]
