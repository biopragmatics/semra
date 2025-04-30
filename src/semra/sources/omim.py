"""Get OMIM gene mappings."""

import pandas as pd
from pyobo import Reference

from semra.rules import EXACT_MATCH, UNSPECIFIED_MAPPING
from semra.struct import Mapping, MappingSet, SimpleEvidence

__all__ = ["get_omim_gene_mappings"]

URL = "https://omim.org/static/omim/data/mim2gene.txt"


def get_omim_gene_mappings() -> list[Mapping]:
    """Get gene mappings from OMIM."""
    df = pd.read_csv(URL, sep="\t", dtype=str, skiprows=4)
    mapping_set = MappingSet(name="OMIM", confidence=0.99)
    rv = []
    for identifier, _type, entrez_id, _hgnc_symbol, ensembl_id in df.values:
        subject = Reference(prefix="omim", identifier=identifier)
        if pd.notna(entrez_id):
            mapping = Mapping(
                subject=subject,
                predicate=EXACT_MATCH,
                object=Reference(prefix="ncbigene", identifier=entrez_id),
                evidence=[
                    SimpleEvidence(justification=UNSPECIFIED_MAPPING, mapping_set=mapping_set)
                ],
            )
            rv.append(mapping)
        # TODO handle dependencies for mapping gene symbol
        if pd.notna(ensembl_id):
            mapping = Mapping(
                subject=subject,
                predicate=EXACT_MATCH,
                object=Reference(prefix="ensembl", identifier=ensembl_id),
                evidence=[
                    SimpleEvidence(justification=UNSPECIFIED_MAPPING, mapping_set=mapping_set)
                ],
            )
            rv.append(mapping)
    return rv
