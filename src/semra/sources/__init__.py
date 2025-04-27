"""Sources of xrefs not from OBO."""

import itertools as itt
import typing as t
from collections.abc import Callable
from typing import Any

from class_resolver import FunctionResolver

from semra.sources.biopragmatics import (
    from_biomappings_negative,
    from_biomappings_predicted,
    get_biomappings_positive_mappings,
)
from semra.sources.cbms2019 import get_cbms2019_mappings
from semra.sources.clo import get_clo_mappings
from semra.sources.compath import get_compath_mappings
from semra.sources.famplex import get_fplx_mappings
from semra.sources.gilda import get_gilda_mappings
from semra.sources.intact import get_intact_complexportal_mappings, get_intact_reactome_mappings
from semra.sources.ncit import (
    get_ncit_chebi_mappings,
    get_ncit_go_mappings,
    get_ncit_hgnc_mappings,
    get_ncit_uniprot_mappings,
)
from semra.sources.omim import get_omim_gene_mappings
from semra.sources.pubchem import get_pubchem_mesh_mappings
from semra.sources.wikidata import get_wikidata_mappings
from semra.struct import Mapping

__all__ = [
    "SOURCE_RESOLVER",
    "from_biomappings_negative",
    "from_biomappings_predicted",
    "get_biomappings_positive_mappings",
    "get_cbms2019_mappings",
    "get_clo_mappings",
    "get_compath_mappings",
    "get_custom",
    "get_fplx_mappings",
    "get_gilda_mappings",
    "get_intact_complexportal_mappings",
    "get_intact_reactome_mappings",
    "get_ncit_chebi_mappings",
    "get_ncit_go_mappings",
    "get_ncit_hgnc_mappings",
    "get_ncit_uniprot_mappings",
    "get_omim_gene_mappings",
    "get_pubchem_mesh_mappings",
    "get_wikidata_mappings",
]

SOURCE_RESOLVER: FunctionResolver[[], list[Mapping]] = FunctionResolver(
    [
        get_intact_reactome_mappings,
        get_intact_complexportal_mappings,
        get_fplx_mappings,
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
        get_wikidata_mappings,  # type:ignore
        get_omim_gene_mappings,
        get_cbms2019_mappings,
        get_compath_mappings,
    ]
)


def _normalize_name(func: Callable[..., Any]) -> str:
    if not func.__name__.startswith("get_"):
        raise NameError(f"Custom source function name does not start with `_get`: {func.__name__}")
    if not func.__name__.endswith("_mappings"):
        raise NameError(
            f"Custom source function name does not end with `_mappings`: {func.__name__}"
        )
    return func.__name__[len("get_") : -len("_mappings")]


# Add synonyms for short name
for func_ in SOURCE_RESOLVER:
    key = _normalize_name(func_)
    norm_key = SOURCE_RESOLVER.normalize(key)
    SOURCE_RESOLVER.synonyms[norm_key] = func_


def get_custom() -> t.Iterable[Mapping]:
    """Get all custom mappings."""
    return itt.chain.from_iterable(func() for func in SOURCE_RESOLVER)
