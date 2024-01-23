"""Get mappings from NCIT."""

from __future__ import annotations

from functools import lru_cache
from typing import Callable

import bioregistry
import pandas as pd
import requests
from curies import Reference
from tqdm.asyncio import tqdm

from semra.rules import EXACT_MATCH, UNSPECIFIED_MAPPING
from semra.struct import Evidence, Mapping, MappingSet, SimpleEvidence

__all__ = [
    "get_ncit_hgnc_mappings",
    "get_ncit_chebi_mappings",
    "get_ncit_go_mappings",
    "get_ncit_uniprot_mappings",
]


BASE = "https://evs.nci.nih.gov/ftp1/NCI_Thesaurus/Mappings"

#: first column NCIT, second column HGNC with banana
HGNC_MAPPINGS_URL = f"{BASE}/NCIt-HGNC_Mapping.txt"
#: first column GO identifiers given with banana, second column NCIT
GO_MAPPINGS_URL = f"{BASE}/GO-NCIt_Mapping.txt"
#: first column NCIT, second column CHEBI with banana
CHEBI_MAPPINGS_URL = f"{BASE}/NCIt-ChEBI_Mapping.txt"
#: first column NCIT, second column UniProt (no banana), third column name
SWISSPROT_MAPPINGS_URL = f"{BASE}/NCIt-SwissProt_Mapping.txt"
#: single line og text
VERSION_URL = f"{BASE}/NCIt_Mapping_Version.txt"
CONFIDENCE = 0.99


@lru_cache(1)
def _get_version() -> str:
    """Get the current NCIT version."""
    return requests.get(VERSION_URL, timeout=20).text.strip()


def _get_evidence() -> SimpleEvidence:
    version = _get_version()
    license = bioregistry.get_license("ncit")
    return SimpleEvidence(
        justification=UNSPECIFIED_MAPPING,
        mapping_set=MappingSet(name="ncit", version=version, license=license, confidence=CONFIDENCE),
    )


def get_ncit_hgnc_mappings() -> list[Mapping]:
    df = pd.read_csv(HGNC_MAPPINGS_URL, sep="\t", header=None, names=["ncit", "hgnc"])
    df["hgnc"] = df["hgnc"].map(lambda s: s.removeprefix("HGNC:"))  # type:ignore
    return _df_to_mappings(
        df,
        source_prefix="ncit",
        target_prefix="hgnc",
        evidence=_get_evidence,
    )


def get_ncit_go_mappings() -> list[Mapping]:
    df = pd.read_csv(HGNC_MAPPINGS_URL, sep="\t", header=None, names=["go", "ncit"])
    df["go"] = df["go"].map(lambda s: s.removeprefix("GO:"))  # type:ignore
    return _df_to_mappings(
        df,
        source_prefix="ncit",
        target_prefix="go",
        evidence=_get_evidence,
    )


def get_ncit_chebi_mappings() -> list[Mapping]:
    df = pd.read_csv(HGNC_MAPPINGS_URL, sep="\t", header=None, names=["ncit", "chebi"])
    df["chebi"] = df["chebi"].map(lambda s: s.removeprefix("CHEBI:"))  # type:ignore
    return _df_to_mappings(
        df,
        source_prefix="ncit",
        target_prefix="chebi",
        evidence=_get_evidence,
    )


def get_ncit_uniprot_mappings() -> list[Mapping]:
    df = pd.read_csv(SWISSPROT_MAPPINGS_URL, sep="\t", header=None, names=["ncit", "uniprot"])
    return _df_to_mappings(
        df,
        source_prefix="ncit",
        target_prefix="uniprot",
        evidence=_get_evidence,
    )


def _df_to_mappings(
    df,
    *,
    source_prefix: str,
    target_prefix: str,
    evidence: Callable[[], Evidence],
    source_identifier_column: str | None = None,
    target_identifier_column: str | None = None,
) -> list[Mapping]:
    if source_identifier_column is None:
        source_identifier_column = source_prefix
    if target_identifier_column is None:
        target_identifier_column = target_prefix
    return [
        Mapping(
            s=Reference(prefix=source_prefix, identifier=source_id),
            p=EXACT_MATCH,
            o=Reference(prefix=target_prefix, identifier=target_id),
            evidence=[evidence()],
        )
        for source_id, target_id in tqdm(
            df[[source_identifier_column, target_identifier_column]].values,
            unit="mapping",
            unit_scale=True,
            desc=f"Processing {source_prefix}",
        )
    ]


if __name__ == "__main__":
    from semra.api import print_source_target_counts

    print_source_target_counts(get_ncit_hgnc_mappings())
