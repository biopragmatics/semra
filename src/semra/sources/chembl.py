"""Get mappings from ChEMBL."""

from __future__ import annotations

import bioregistry
from pyobo import Reference
from tqdm import tqdm

from semra.rules import EXACT_MATCH, UNSPECIFIED_MAPPING
from semra.struct import Mapping, MappingSet, SimpleEvidence

__all__ = [
    "get_chembl_compound_mappings",
    "get_chembl_protein_mappings",
]


def get_chembl_compound_mappings(version: str | None = None) -> list[Mapping]:
    """Get ChEMBL chemical equivalences."""
    import chembl_downloader

    if version is None:
        version = chembl_downloader.latest()
    license = bioregistry.get_license("chembl.compound")
    df = chembl_downloader.get_chemreps_df(version=version)
    rows = []
    for chembl, _smiles, _inchi, inchi_key in tqdm(
        df.values, desc="Get ChEMBL compound mappings", unit="chemical", unit_scale=True
    ):
        s = Reference(prefix="chembl.compound", identifier=chembl)
        rows.append(
            Mapping(
                s=s,
                p=EXACT_MATCH,
                o=Reference(prefix="inchikey", identifier=inchi_key),
                evidence=[
                    SimpleEvidence(
                        justification=UNSPECIFIED_MAPPING,
                        mapping_set=MappingSet(
                            name="chembl", version=version, license=license, confidence=0.99
                        ),
                    )
                ],
            )
        )
    return rows


def get_chembl_protein_mappings(version: str | None = None) -> list[Mapping]:
    """Get ChEMBL to protein mappings."""
    import chembl_downloader

    if version is None:
        version = chembl_downloader.latest()
    license = bioregistry.get_license("chembl.compound")
    # columns: "uniprot_id", "chembl_target_id", "name", "type"
    df = chembl_downloader.get_uniprot_mapping_df(version=version)
    return [
        Mapping(
            s=Reference(prefix="chembl.target", identifier=chembl_id),
            p=EXACT_MATCH,
            o=Reference(prefix="uniprot", identifier=uniprot),
            evidence=[
                SimpleEvidence(
                    justification=UNSPECIFIED_MAPPING,
                    mapping_set=MappingSet(
                        name="chembl", version=version, license=license, confidence=0.99
                    ),
                )
            ],
        )
        for uniprot, chembl_id, _name, _type in tqdm(
            df.values, desc="Get ChEMBL protein mappings", unit="protein", unit_scale=True
        )
    ]


if __name__ == "__main__":
    get_chembl_protein_mappings()
    get_chembl_compound_mappings()
