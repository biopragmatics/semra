"""Cross references from cbms2019.

.. seealso::

    https://github.com/pantapps/cbms2019 and https://doi.org/10.1109/CBMS.2019.00044
"""

import pandas as pd
from pydantic import ValidationError
from pyobo import Reference
from tqdm import tqdm

from semra.rules import CHAIN_MAPPING, EXACT_MATCH, UNSPECIFIED_MAPPING
from semra.struct import Mapping, MappingSet, SimpleEvidence

__all__ = [
    "get_cbms2019_mappings",
]

#: Columns: DOID, DO name, xref xb, xref ix
base_url = "https://raw.githubusercontent.com/pantapps/cbms2019/master"
doid_to_all = f"{base_url}/mesh_icd10cm_via_do_not_mapped_umls.tsv"
#: Columns: SNOMEDCT_ID, SNOMEDCIT_NAME, ICD10CM_ID, ICD10CM_NAME, MESH_ID
all_to_all = f"{base_url}/mesh_icd10cm_via_snomedct_not_mapped_umls.tsv"
#: Columns: DOID, DO name, xref xb, xref ix
doid_to_all_2 = f"{base_url}/mesh_snomedct_via_do_not_mapped_umls.tsv"
#: Columns: SNOMEDCT_ID, SNOMEDCIT_NAME, ICD10CM_ID, ICD10CM_NAME, MESH_ID
all_to_all_2 = f"{base_url}/mesh_snomedct_via_icd10cm_not_mapped_umls.tsv"

CONFIDENCE = 0.8
NSM = {
    "MESH": "mesh",
    "ICD10CM": "icd10cm",
    "SNOMEDCT_US_2016_03_01": "snomedct",
}


def _get_doid(url: str) -> list[Mapping]:
    df = pd.read_csv(url, sep="\t", usecols=["DO_ID", "resource", "resource_ID"])
    rv = []
    evidence = SimpleEvidence(
        mapping_set=MappingSet(name=url, confidence=CONFIDENCE),
        justification=CHAIN_MAPPING,
    )
    for do_id, target_prefix, target_id in df.values:
        try:
            obj = Reference(prefix=NSM[target_prefix], identifier=target_id)
        except ValidationError:
            tqdm.write(f"[doid:{do_id}] failed to parse xref {target_prefix}:{target_id}")
            continue
        mapping = Mapping(
            subject=Reference(prefix="doid", identifier=do_id.removeprefix("DOID:")),
            predicate=EXACT_MATCH,
            object=obj,
            evidence=[evidence],
        )
        rv.append(mapping)

    return rv


def _get_mesh_to_icd_via_doid() -> list[Mapping]:
    return _get_doid(doid_to_all)


def _get_mesh_to_icd_via_snomedct() -> list[Mapping]:
    df = pd.read_csv(all_to_all, sep="\t", usecols=["SNOMEDCT_ID", "ICD10CM_ID", "MESH_ID"])
    rows = []
    for snomedct_id, icd_id, mesh_id in df.values:
        snomed_ref = Reference(prefix="snomedct", identifier=str(int(snomedct_id)))
        mesh_ref = Reference(prefix="mesh", identifier=mesh_id)
        rows.append(
            Mapping(
                subject=mesh_ref,
                predicate=EXACT_MATCH,
                object=snomed_ref,
                evidence=[
                    SimpleEvidence(
                        mapping_set=MappingSet(
                            name=all_to_all_2,
                            confidence=CONFIDENCE,
                        ),
                        justification=UNSPECIFIED_MAPPING,
                    )
                ],
            )
        )

        try:
            icd_ref = Reference(prefix="icd", identifier=icd_id)
        except ValidationError:
            pass
            # tqdm.write(f"failed to parse ICD: {icd_id}")
        else:
            rows.append(
                Mapping(
                    subject=mesh_ref,
                    predicate=EXACT_MATCH,
                    object=icd_ref,
                    evidence=[
                        SimpleEvidence(
                            mapping_set=MappingSet(
                                name=all_to_all_2,
                                confidence=CONFIDENCE,
                            ),
                            justification=CHAIN_MAPPING,
                        )
                    ],
                )
            )
            rows.append(
                Mapping(
                    subject=icd_ref,
                    predicate=EXACT_MATCH,
                    object=snomed_ref,
                    evidence=[
                        SimpleEvidence(
                            mapping_set=MappingSet(
                                name=all_to_all_2,
                                confidence=CONFIDENCE,
                            ),
                            justification=UNSPECIFIED_MAPPING,
                        )
                    ],
                )
            )
    return rows


def _get_mesh_to_snomedct_via_doid() -> list[Mapping]:
    return _get_doid(doid_to_all_2)


def _get_mesh_to_snomedct_via_icd() -> list[Mapping]:
    df = pd.read_csv(
        all_to_all_2,
        sep="\t",
        usecols=["SNOMEDCT_ID", "ICD10CM_ID", "MESH_ID"],
        dtype={"SNOMEDCT_ID": float},
    )
    rows = []
    for snomedct_id, icd_id, mesh_id in df.values:
        snomed_ref = Reference(prefix="snomedct", identifier=str(int(snomedct_id)))
        mesh_ref = Reference(prefix="mesh", identifier=mesh_id)
        rows.append(
            Mapping(
                subject=mesh_ref,
                predicate=EXACT_MATCH,
                object=snomed_ref,
                evidence=[
                    SimpleEvidence(
                        mapping_set=MappingSet(
                            name=all_to_all_2,
                            confidence=CONFIDENCE,
                        ),
                        justification=CHAIN_MAPPING,
                    )
                ],
            )
        )

        try:
            icd_ref = Reference(prefix="icd", identifier=icd_id)
        except ValidationError:
            # tqdm.write(f"failed to parse ICD {icd_id}")
            pass
        else:
            rows.append(
                Mapping(
                    subject=mesh_ref,
                    predicate=EXACT_MATCH,
                    object=icd_ref,
                    evidence=[
                        SimpleEvidence(
                            mapping_set=MappingSet(
                                name=all_to_all_2,
                                confidence=CONFIDENCE,
                            ),
                            justification=UNSPECIFIED_MAPPING,
                        )
                    ],
                )
            )
            rows.append(
                Mapping(
                    subject=icd_ref,
                    predicate=EXACT_MATCH,
                    object=snomed_ref,
                    evidence=[
                        SimpleEvidence(
                            mapping_set=MappingSet(
                                name=all_to_all_2,
                                confidence=CONFIDENCE,
                            ),
                            justification=UNSPECIFIED_MAPPING,
                        )
                    ],
                )
            )
    return rows


def get_cbms2019_mappings() -> list[Mapping]:
    """Get all CBMS2019 xrefs."""
    return [
        *_get_mesh_to_icd_via_doid(),
        *_get_mesh_to_icd_via_snomedct(),
        *_get_mesh_to_snomedct_via_doid(),
        *_get_mesh_to_snomedct_via_icd(),
    ]
