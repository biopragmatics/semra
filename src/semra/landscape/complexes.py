"""A configuration for assembling mappings for protein complex terms."""

import pystow
from curies import Reference
from curies.vocabulary import charlie

from semra.pipeline import Configuration, Input, Mutation

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
}

CONFIGURATION = Configuration(
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
    raw_pickle_path=MODULE.join(name="raw.pkl"),
    raw_sssom_path=MODULE.join(name="raw.sssom.tsv"),
    raw_neo4j_path=MODULE.join("neo4j_raw"),
    raw_neo4j_name="semra-complex",
    processed_pickle_path=MODULE.join(name="processed.pkl"),
    processed_sssom_path=MODULE.join(name="processed.sssom.tsv"),
    processed_neo4j_path=MODULE.join("neo4j"),
    processed_neo4j_name="semra-complex",
    priority_pickle_path=MODULE.join(name="priority.pkl"),
    priority_sssom_path=MODULE.join(name="priority.sssom.tsv"),
    configuration_path=MODULE.join(name="configuration.json"),
    zenodo_record=11091422,
)


if __name__ == "__main__":
    CONFIGURATION.cli()
