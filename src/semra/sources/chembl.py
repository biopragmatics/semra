"""Get mappings from ChEMBL."""

import chembl_downloader

from semra.rules import EXACT_MATCH
from semra.struct import Mapping, Reference, SimpleEvidence

__all__ = [
    "get_chembl_compound_mappings",
    "get_chembl_protein_mappings",
]


def get_chembl_compound_mappings(version: str | None = None) -> list[Mapping]:
    """Get ChEMBL chemical equivalences."""
    if version is None:
        version = chembl_downloader.latest()
    df = chembl_downloader.get_chemreps_df(version=version)
    rows = []
    for chembl, _smiles, _inchi, inchi_key in df.values:
        s = Reference(prefix="chembl.compound", identifier=chembl)
        rows.append(Mapping(s=s, p=EXACT_MATCH, o=Reference(prefix="inchikey", identifier=inchi_key)))
    return rows


def get_chembl_protein_mappings(version: str | None = None) -> list[Mapping]:
    """Get ChEMBL to protein mappings."""
    if version is None:
        version = chembl_downloader.latest()
    # columns: "uniprot_id", "chembl_target_id", "name", "type"
    df = chembl_downloader.get_uniprot_mapping_df(version=version)
    return [
        Mapping(
            s=Reference(prefix="uniprot", identifier=uniprot),
            p=EXACT_MATCH,
            o=Reference(prefix="chembl.target", identifier=chembl_id),
            evidence=[SimpleEvidence(mapping_set="chembl", mapping_set_version=version, confidence=0.99)],
        )
        for uniprot, chembl_id, _name, _type in df.values
    ]
