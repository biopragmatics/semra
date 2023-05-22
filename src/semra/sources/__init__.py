"""Sources of xrefs not from OBO."""

import itertools as itt
from collections.abc import Callable, Iterable

from class_resolver import FunctionResolver

from semra import Mapping
from semra.sources.biopragmatics import from_biomappings_negative, from_biomappings_positive, from_biomappings_predicted
from semra.sources.chembl import get_chembl_compound_mappings, get_chembl_protein_mappings
from semra.sources.famplex import get_famplex_mappings
from semra.sources.gilda import from_gilda
from semra.sources.intact import get_intact_complexportal_mappings, get_intact_reactome_mappings
from semra.sources.ncit import (
    get_ncit_chebi_mappings,
    get_ncit_go_mappings,
    get_ncit_hgnc_mappings,
    get_ncit_uniprot_mappings,
)
from semra.sources.pubchem import get_pubchem_mesh_mappings

__all__ = [
    "get_chembl_compound_mappings",
    "get_ncit_chebi_mappings",
    "get_ncit_uniprot_mappings",
    "get_ncit_go_mappings",
    "get_ncit_hgnc_mappings",
    "get_pubchem_mesh_mappings",
    "get_chembl_protein_mappings",
    "get_famplex_mappings",
    "get_intact_complexportal_mappings",
    "get_intact_reactome_mappings",
    "get_custom",
    "from_biomappings_positive",
    "from_biomappings_predicted",
    "from_biomappings_negative",
    "from_gilda",
]

SOURCE_RESOLVER: FunctionResolver[Callable[[], list[Mapping]]] = FunctionResolver(
    [
        get_chembl_compound_mappings,
        get_chembl_protein_mappings,
        get_intact_reactome_mappings,
        get_intact_complexportal_mappings,
        get_famplex_mappings,
        get_pubchem_mesh_mappings,
        get_ncit_chebi_mappings,
        get_ncit_hgnc_mappings,
        get_ncit_go_mappings,
        get_ncit_uniprot_mappings,
        from_biomappings_positive,
        from_gilda,
    ]
)


def get_custom() -> Iterable[Mapping]:
    """Get all custom mappings."""
    return itt.chain.from_iterable(func() for func in SOURCE_RESOLVER)
