"""Sources of xrefs not from OBO."""

import itertools as itt
import typing as t

from class_resolver import FunctionResolver

from semra.sources.biopragmatics import (
    from_biomappings_negative,
    from_biomappings_predicted,
    get_biomappings_positive_mappings,
)
from semra.sources.chembl import get_chembl_compound_mappings, get_chembl_protein_mappings
from semra.sources.clo import get_clo_mappings
from semra.sources.famplex import get_famplex_mappings
from semra.sources.gilda import get_gilda_mappings
from semra.sources.intact import get_intact_complexportal_mappings, get_intact_reactome_mappings
from semra.sources.ncit import (
    get_ncit_chebi_mappings,
    get_ncit_go_mappings,
    get_ncit_hgnc_mappings,
    get_ncit_uniprot_mappings,
)
from semra.sources.pubchem import get_pubchem_mesh_mappings
from semra.struct import Mapping

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
    "get_biomappings_positive_mappings",
    "from_biomappings_predicted",
    "from_biomappings_negative",
    "get_gilda_mappings",
    "get_clo_mappings",
]

SOURCE_RESOLVER: FunctionResolver[t.Callable[[], t.List[Mapping]]] = FunctionResolver(
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
        # from_biomappings_negative,
        # from_biomappings_predicted,
        get_biomappings_positive_mappings,
        get_gilda_mappings,
        get_clo_mappings,
    ]
)

# Add synonyms for short name
for func in SOURCE_RESOLVER:
    if not func.__name__.startswith("get_"):
        raise NameError(f"Custom source function name does not start with `_get`: {func.__name__}")
    if not func.__name__.endswith("_mappings"):
        raise NameError(f"Custom source function name does not end with `_mappings`: {func.__name__}")
    key = func.__name__[len("get_") : -len("_mappings")]
    norm_key = SOURCE_RESOLVER.normalize(key)
    SOURCE_RESOLVER.synonyms[norm_key] = func


def get_custom() -> t.Iterable[Mapping]:
    """Get all custom mappings."""
    return itt.chain.from_iterable(func() for func in SOURCE_RESOLVER)
