"""A configuration for assembling mappings for anatomical terms."""

import pystow
from pyobo.sources.mesh import get_mesh_category_references

import semra
from semra import Reference
from semra.rules import charlie

__all__ = [
    "CONFIGURATION",
    "MODULE",
]

MODULE = pystow.module("semra", "case-studies", "anatomy")
PRIORITY = [
    "uberon",
    "mesh",
    "bto",
    "caro",
    "ncit",
    "umls",
]
# some resources are generic, so we want to cut to a relevant subset
SUBSETS = {
    "mesh": get_mesh_category_references("A", skip=["A11"]),
    "ncit": [Reference.from_curie("ncit:C12219")],
    "umls": [
        # see https://uts.nlm.nih.gov/uts/umls/semantic-network/root
        Reference.from_curie("sty:T024"),  # tissue
        Reference.from_curie("sty:T017"),  # anatomical structure
    ],
}

CONFIGURATION = semra.Configuration(
    key="anatomy",
    name="SeMRA Anatomy Mappings Database",
    description="Supports the analysis of the landscape of anatomy nomenclature resources.",
    creators=[charlie],
    inputs=[
        semra.Input(source="biomappings"),
        semra.Input(source="gilda"),
        semra.Input(prefix="uberon", source="pyobo", confidence=0.99),
        semra.Input(prefix="bto", source="pyobo", confidence=0.99),
        semra.Input(prefix="caro", source="pyobo", confidence=0.99),
        semra.Input(prefix="mesh", source="pyobo", confidence=0.99),
        semra.Input(prefix="ncit", source="pyobo", confidence=0.99),
        semra.Input(prefix="umls", source="pyobo", confidence=0.99),
    ],
    subsets=SUBSETS,
    add_labels=False,
    priority=PRIORITY,
    keep_prefixes=PRIORITY,
    remove_imprecise=False,
    mutations=[
        semra.Mutation(source="uberon", confidence=0.8),
        semra.Mutation(source="bto", confidence=0.65),
        semra.Mutation(source="caro", confidence=0.8),
        semra.Mutation(source="ncit", confidence=0.7),
        semra.Mutation(source="umls", confidence=0.7),
    ],
    zenodo_record=11091803,
    directory=MODULE.base,
)


if __name__ == "__main__":
    CONFIGURATION.cli()
