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
    raw_pickle_path=MODULE.join(name="raw.pkl"),
    raw_sssom_path=MODULE.join(name="raw.sssom.tsv"),
    # raw_neo4j_path=MODULE.join("neo4j_raw"),
    processed_pickle_path=MODULE.join(name="processed.pkl"),
    processed_sssom_path=MODULE.join(name="processed.sssom.tsv"),
    processed_neo4j_path=MODULE.join("neo4j"),
    processed_neo4j_name="semra-taxrank",
    priority_pickle_path=MODULE.join(name="priority.pkl"),
    priority_sssom_path=MODULE.join(name="priority.sssom.tsv"),
    configuration_path=MODULE.join(name="configuration.json"),
)

if __name__ == "__main__":
    CONFIGURATION.cli()
