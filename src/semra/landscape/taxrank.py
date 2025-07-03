"""A configuration for assembling mappings for taxonomical rank terms."""

import pystow

import semra
from semra.rules import charlie

__all__ = [
    "MODULE",
    "TAXRANK_CONFIGURATION",
]

MODULE = pystow.module("semra", "case-studies", "taxranks")
PRIORITY = [
    "taxrank",
    "ncbitaxon",
    "tdwg.taxonrank",
]
SUBSETS = {"ncbitaxon": [semra.Reference(prefix="ncbitaxon", identifier="taxonomic_rank")]}

TAXRANK_CONFIGURATION = semra.Configuration(
    key="taxrank",
    name="SeMRA Taxonomical Ranks Mappings Database",
    description="Supports the analysis of the landscape of taxnomical rank nomenclature resources.",
    creators=[charlie],
    inputs=[
        semra.Input(prefix="taxrank", source="pyobo", confidence=0.99),
    ],
    subsets=SUBSETS,
    add_labels=False,
    priority=PRIORITY,
    remove_imprecise=False,
    mutations=[
        semra.Mutation(source="taxrank", confidence=0.99),
    ],
    directory=MODULE.base,
)

if __name__ == "__main__":
    TAXRANK_CONFIGURATION.cli()
