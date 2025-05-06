"""A configuration for assembling mappings for disease terms."""

import bioregistry
import pystow
from pyobo.sources.mesh import get_mesh_category_references

from semra import Reference
from semra.pipeline import Configuration, Input, Mutation
from semra.rules import charlie

__all__ = [
    "CONFIGURATION",
    "MODULE",
]

ICD_PREFIXES = bioregistry.get_collection("0000004").resources  # type:ignore
MODULE = pystow.module("semra", "case-studies", "disease")
PREFIXES = PRIORITY = [
    "doid",
    "mondo",
    "efo",
    "mesh",
    "ncit",
    "orphanet",
    "orphanet.ordo",
    "umls",
    "omim",
    "omim.ps",
    # "snomedct",
    "gard",
    *ICD_PREFIXES,
]
# some resources are generic, so we want to cut to a relevant subset
SUBSETS = {
    "mesh": [*get_mesh_category_references("C"), *get_mesh_category_references("F")],
    "efo": [Reference.from_curie("efo:0000408")],
    "ncit": [Reference.from_curie("ncit:C2991")],
    "umls": [
        # all children of https://uts.nlm.nih.gov/uts/umls/semantic-network/Pathologic%20Function
        Reference.from_curie("sty:T049"),  # cell or molecular dysfunction
        Reference.from_curie("sty:T047"),  # disease or syndrome
        Reference.from_curie("sty:T191"),  # neoplastic process
        Reference.from_curie("sty:T050"),  # experimental model of disease
        Reference.from_curie("sty:T048"),  # mental or behavioral dysfunction
    ],
}

CONFIGURATION = Configuration(
    key="disease",
    name="SeMRA Disease Mappings Database",
    description="Supports the analysis of the landscape of disease nomenclature resources.",
    creators=[charlie],
    inputs=[
        Input(source="biomappings"),
        Input(source="gilda"),
        Input(prefix="doid", source="bioontologies", confidence=0.99),
        Input(prefix="mondo", source="bioontologies", confidence=0.99),
        Input(prefix="efo", source="bioontologies", confidence=0.99),
        Input(prefix="mesh", source="pyobo", confidence=0.99),
        Input(prefix="ncit", source="bioontologies", confidence=0.85),
        Input(prefix="umls", source="pyobo", confidence=0.9),
        Input(prefix="orphanet.ordo", source="bioontologies", confidence=0.9),
        # Input(prefix="orphanet", source="bioontologies", confidence=0.9),
        # Input(prefix="hp", source="bioontologies", confidence=0.99),
    ],
    subsets=SUBSETS,
    add_labels=True,
    priority=PRIORITY,
    keep_prefixes=PREFIXES,
    remove_imprecise=False,
    mutations=[
        Mutation(source="doid", confidence=0.95),
        Mutation(source="mondo", confidence=0.95),
        Mutation(source="efo", confidence=0.90),
        Mutation(source="ncit", confidence=0.7),
        Mutation(source="umls", confidence=0.7),
        Mutation(source="orphanet.ordo", confidence=0.7),
        Mutation(source="orphanet", confidence=0.7),
        # Mutation(source="hp", confidence=0.7),
    ],
    zenodo_record=11091886,
    directory=MODULE.base,
)


if __name__ == "__main__":
    CONFIGURATION.cli()
