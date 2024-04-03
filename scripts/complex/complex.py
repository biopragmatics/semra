"""Protein complex mappings."""

import click
import pystow

from semra.pipeline import Configuration, Input

MODULE = pystow.module("semra", "case-studies", "complex")
PREFIXES = PRIORITY = [
    "complexportal",
    "fplx",
    "go",
    "chembl.target",
    "wikidata",
    "scomp",
]
SUBSETS = {
    "go": ["go:0032991"],
}

CONFIGURATION = Configuration(
    name="Protein Complex Landscape Analysis",
    description="Analyze the landscape of protein complex nomenclature resources, species-agnostic.",
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
    priority=PRIORITY,
    post_keep_prefixes=PREFIXES,
    remove_imprecise=False,
    # mutations=[
    #     Mutation(source="hgnc", confidence=0.95),
    # ],
    raw_pickle_path=MODULE.join(name="raw.pkl"),
    raw_sssom_path=MODULE.join(name="raw.sssom.tsv"),
    # raw_neo4j_path=MODULE.join("neo4j_raw"),
    processed_pickle_path=MODULE.join(name="processed.pkl"),
    processed_sssom_path=MODULE.join(name="processed.sssom.tsv"),
    processed_neo4j_path=MODULE.join("neo4j"),
    processed_neo4j_name="semra-complex",
    priority_pickle_path=MODULE.join(name="priority.pkl"),
    priority_sssom_path=MODULE.join(name="priority.sssom.tsv"),
)


@click.command()
def main():
    """Get the protein complex landscape."""
    CONFIGURATION.get_mappings(refresh_raw=True, refresh_processed=True)


if __name__ == "__main__":
    main()
