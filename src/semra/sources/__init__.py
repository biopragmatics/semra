"""Sources of xrefs not from OBO."""

import itertools as itt
import typing as t
from collections.abc import Callable
from typing import Any

from class_resolver import FunctionResolver
from sssom_pydantic import SemanticMapping

from .biopragmatics import (
    get_biomappings_negative_mappings,
    get_biomappings_positive_mappings,
    get_biomappings_predicted_mappings,
)
from .cbms2019 import get_cbms2019_mappings
from .clo import get_clo_mappings
from .compath import get_compath_mappings
from .famplex import get_fplx_mappings
from .gilda import get_gilda_mappings
from .ncit import (
    get_ncit_chebi_mappings,
    get_ncit_go_mappings,
    get_ncit_hgnc_mappings,
    get_ncit_uniprot_mappings,
)
from .omim import get_omim_gene_mappings
from .pubchem import get_pubchem_mesh_mappings
from .wikidata import get_wikidata_mappings

__all__ = [
    "SOURCE_RESOLVER",
    "get_biomappings_negative_mappings",
    "get_biomappings_positive_mappings",
    "get_biomappings_predicted_mappings",
    "get_cbms2019_mappings",
    "get_clo_mappings",
    "get_compath_mappings",
    "get_custom",
    "get_fplx_mappings",
    "get_gilda_mappings",
    "get_ncit_chebi_mappings",
    "get_ncit_go_mappings",
    "get_ncit_hgnc_mappings",
    "get_ncit_uniprot_mappings",
    "get_omim_gene_mappings",
    "get_pubchem_mesh_mappings",
    "get_wikidata_mappings",
    "normalize_custom_func_name",
]

SOURCE_RESOLVER: FunctionResolver[[], list[SemanticMapping]] = FunctionResolver(
    [
        get_fplx_mappings,
        get_pubchem_mesh_mappings,
        get_ncit_chebi_mappings,
        get_ncit_hgnc_mappings,
        get_ncit_go_mappings,
        get_ncit_uniprot_mappings,
        get_biomappings_negative_mappings,
        get_biomappings_predicted_mappings,
        get_biomappings_positive_mappings,
        get_gilda_mappings,
        get_clo_mappings,
        get_wikidata_mappings,  # type:ignore
        get_omim_gene_mappings,
        get_cbms2019_mappings,
        get_compath_mappings,
    ]
)


def normalize_custom_func_name(func: Callable[..., Any]) -> str:
    """Normalize custom function name."""
    if not func.__name__.startswith("get_"):
        raise NameError(f"Custom source function name does not start with `_get`: {func.__name__}")
    if not func.__name__.endswith("_mappings"):
        raise NameError(
            f"Custom source function name does not end with `_mappings`: {func.__name__}"
        )
    return func.__name__[len("get_") : -len("_mappings")]


# Add synonyms for short name
for func_ in SOURCE_RESOLVER:
    key = normalize_custom_func_name(func_)
    norm_key = SOURCE_RESOLVER.normalize(key)
    SOURCE_RESOLVER.synonyms[norm_key] = func_


def get_custom() -> t.Iterable[SemanticMapping]:
    """Get all custom mappings."""
    return itt.chain.from_iterable(func() for func in SOURCE_RESOLVER)
