"""A configuration for assembling mappings for taxonomical rank terms."""

import pystow

import semra
from semra.rules import charlie

__all__ = [
    "CONFIGURATION",
    "MODULE",
]

MODULE = pystow.module("semra", "case-studies", "taxranks")
PRIORITY = [
    "taxrank",
    "ncbitaxon",
    "tdwg.taxonrank",
]

CONFIGURATION = semra.Configuration(
    key="taxrank",
    name="SeMRA Taxonomical Ranks Mappings Database",
    description="Supports the analysis of the landscape of taxnomical rank nomenclature resources.",
    creators=[charlie],
    inputs=[
        semra.Input(prefix="taxrank", source="pyobo", confidence=0.99),
    ],
    add_labels=False,
    priority=PRIORITY,
    remove_imprecise=False,
    mutations=[
        semra.Mutation(source="taxrank", confidence=0.99),
    ],
    directory=MODULE.base,
)

if __name__ == "__main__":
    CONFIGURATION.cli()
