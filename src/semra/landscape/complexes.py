"""A configuration for assembling mappings for protein complex terms."""

import pystow

from semra import Reference
from semra.pipeline import Configuration, Input, Mutation
from semra.rules import charlie

__all__ = [
    "CONFIGURATION",
    "MODULE",
]

MODULE = pystow.module("semra", "case-studies", "complex")
PREFIXES = PRIORITY = [
    "complexportal",
    "fplx",
    "go",
    "chembl.target",
    "wikidata",
    "scomp",
    # "reactome", # TODO need a subset in Reactome to make this useful
    "signor",
    "intact",
]
SUBSETS = {
    "go": [Reference.from_curie("go:0032991")],
    "chembl.target": [
        Reference(prefix="obo", identifier="chembl.target#protein-complex"),
        Reference(prefix="obo", identifier="chembl.target#protein-complex-group"),
        Reference(prefix="obo", identifier="chembl.target#protein-nucleic-acid-complex"),
    ],
}

CONFIGURATION = Configuration(
    key="complex",
    name="SeMRA Protein Complex Landscape Analysis",
    description="Analyze the landscape of protein complex nomenclature "
    "resources, species-agnostic.",
    creators=[charlie],
    inputs=[
        Input(source="gilda"),
        Input(source="biomappings"),
        Input(prefix="fplx", source="pyobo", confidence=0.99),
        Input(prefix="fplx", source="custom", confidence=0.99),
        Input(prefix="intact_complexportal", source="custom", confidence=0.99),
        Input(prefix="complexportal", source="pyobo", confidence=0.99),
        Input(prefix="go", source="pyobo", confidence=0.99),
        # Wikidata has mappings as well
        Input(prefix="complexportal", source="wikidata", confidence=0.99),
        Input(prefix="reactome", source="wikidata", confidence=0.99),
    ],
    add_labels=True,
    subsets=SUBSETS,
    priority=PRIORITY,
    post_keep_prefixes=PREFIXES,
    remove_imprecise=False,
    mutations=[
        Mutation(source="go", confidence=0.95),
    ],
    zenodo_record=11091422,
    directory=MODULE.base,
)


if __name__ == "__main__":
    CONFIGURATION.cli()
