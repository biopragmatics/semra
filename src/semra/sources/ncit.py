"""Get mappings from NCIT."""

from __future__ import annotations

from functools import lru_cache

import bioregistry
import pandas as pd
import pystow
import requests
from pydantic import AnyUrl, ValidationError
from sssom_pydantic import SemanticMapping
from tqdm.asyncio import tqdm

from semra.constants import Reference
from semra.vocabulary import EXACT_MATCH, UNSPECIFIED_MAPPING

__all__ = [
    "get_ncit_chebi_mappings",
    "get_ncit_go_mappings",
    "get_ncit_hgnc_mappings",
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

MODULE = pystow.module("bio", "ncit")


@lru_cache(1)
def _get_version() -> str:
    """Get the current NCIT version."""
    return requests.get(VERSION_URL, timeout=20).text.strip()


def get_ncit_hgnc_mappings(*, force: bool = False) -> list[SemanticMapping]:
    """Get NCIT to HGNC semantic mappings."""
    df = MODULE.ensure_csv(
        url=HGNC_MAPPINGS_URL,
        force=force,
        version=_get_version,
        read_csv_kwargs={"sep": "\t", "header": None, "names": ["ncit", "hgnc"]},
    )
    df["hgnc"] = df["hgnc"].map(lambda s: s.removeprefix("HGNC:"))
    return _df_to_mappings(df, source_prefix="ncit", target_prefix="hgnc", url=HGNC_MAPPINGS_URL)


def get_ncit_go_mappings(*, force: bool = False) -> list[SemanticMapping]:
    """Get NCIT to Gene Ontology (GO) semantic mappings."""
    df = MODULE.ensure_csv(
        url=GO_MAPPINGS_URL,
        force=force,
        version=_get_version,
        read_csv_kwargs={"sep": "\t", "header": None, "names": ["go", "ncit"]},
    )
    df["go"] = df["go"].map(lambda s: s.removeprefix("GO:"))
    return _df_to_mappings(df, source_prefix="ncit", target_prefix="go", url=GO_MAPPINGS_URL)


def get_ncit_chebi_mappings(*, force: bool = False) -> list[SemanticMapping]:
    """Get NCIT to ChEBI semantic mappings."""
    df = MODULE.ensure_csv(
        url=CHEBI_MAPPINGS_URL,
        force=force,
        version=_get_version,
        read_csv_kwargs={"sep": "\t", "header": None, "names": ["ncit", "chebi"]},
    )
    df["chebi"] = df["chebi"].map(lambda s: s.removeprefix("CHEBI:"))
    return _df_to_mappings(df, source_prefix="ncit", target_prefix="chebi", url=CHEBI_MAPPINGS_URL)


def get_ncit_uniprot_mappings(*, force: bool = False) -> list[SemanticMapping]:
    """Get NCIT to UniProt semantic mappings."""
    df = MODULE.ensure_csv(
        url=SWISSPROT_MAPPINGS_URL,
        force=force,
        version=_get_version,
        read_csv_kwargs={"sep": "\t", "usecols": [0, 1]},
    )
    return _df_to_mappings(
        df,
        source_prefix="ncit",
        target_prefix="uniprot",
        source_identifier_column="NCIt Code",
        target_identifier_column="SwissProt ID",
        url=SWISSPROT_MAPPINGS_URL,
    )


def _df_to_mappings(
    df: pd.DataFrame,
    *,
    source_prefix: str,
    target_prefix: str,
    source_identifier_column: str | None = None,
    target_identifier_column: str | None = None,
    url: str,
    confidence: float = CONFIDENCE,
) -> list[SemanticMapping]:
    if source_identifier_column is None:
        source_identifier_column = source_prefix
    if target_identifier_column is None:
        target_identifier_column = target_prefix

    rv = []

    version = _get_version()
    resource = bioregistry.get_resource("ncit", strict=True)
    source = Reference(prefix="bioregistry", identifier="ncit")
    provider = AnyUrl(url)
    license_url = resource.get_license_url()
    for source_id, target_id in tqdm(
        df[[source_identifier_column, target_identifier_column]].values,
        unit="mapping",
        unit_scale=True,
        desc=f"Processing {source_prefix}",
        leave=False,
    ):
        try:
            obj = Reference(prefix=target_prefix, identifier=target_id)
        except ValidationError:
            tqdm.write(f"[ncit:{source_id}] invalid xref: {target_prefix}:{target_id}")
            continue
        mapping = SemanticMapping(
            subject=Reference(prefix=source_prefix, identifier=source_id),
            subject_source_version=version,
            predicate=EXACT_MATCH,
            object=obj,
            justification=UNSPECIFIED_MAPPING,
            license=license_url,
            confidence=confidence,
            source=source,
            provider=provider,
        )
        rv.append(mapping)

    return rv
