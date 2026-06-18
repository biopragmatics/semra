"""Get OMIM gene mappings."""

import bioregistry
import bioversions
import pandas as pd
from pydantic import AnyUrl
from sssom_pydantic import SemanticMapping

from semra.constants import Reference
from semra.vocabulary import EXACT_MATCH, UNSPECIFIED_MAPPING

__all__ = ["get_omim_gene_mappings"]

URL = "https://omim.org/static/omim/data/mim2gene.txt"


def get_omim_gene_mappings(confidence: float = 0.99) -> list[SemanticMapping]:
    """Get gene mappings from OMIM."""
    df = pd.read_csv(URL, sep="\t", dtype=str, skiprows=4)
    license_url = bioregistry.get_license("omim")
    source = Reference(prefix="bioregistry", identifier="omim")
    provider = AnyUrl(URL)
    version = bioversions.get_version("omim")
    rv = []
    for identifier, _type, entrez_id, _hgnc_symbol, ensembl_id in df.values:
        subject = Reference(prefix="omim", identifier=identifier)
        if pd.notna(entrez_id):
            mapping = SemanticMapping(
                subject=subject,
                subject_source_version=version,
                predicate=EXACT_MATCH,
                object=Reference(prefix="ncbigene", identifier=entrez_id),
                justification=UNSPECIFIED_MAPPING,
                source=source,
                provider=provider,
                confidence=confidence,
                license=license_url,
            )
            rv.append(mapping)
        # TODO handle dependencies for mapping gene symbol
        if pd.notna(ensembl_id):
            mapping = SemanticMapping(
                subject=subject,
                subject_source_version=version,
                predicate=EXACT_MATCH,
                object=Reference(prefix="ensembl", identifier=ensembl_id),
                justification=UNSPECIFIED_MAPPING,
                source=source,
                provider=provider,
                license=license_url,
                confidence=confidence,
            )
            rv.append(mapping)
    return rv
