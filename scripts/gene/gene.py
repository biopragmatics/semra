"""Gene mappings."""

import bioregistry
import click
import pystow

from semra.pipeline import Configuration, Input, Mutation

MODULE = pystow.module("semra", "case-studies", "gene")
PREFIXES = PRIORITY = [
    "ncbigene",
    "hgnc",
    "mgi",
    "rgd",
    "cgnc",
    "wormbase",
    "flybase",
    "sgd",
    #
    "omim",
    "civic.gid",
    #
    "umls",
    "ncit",
    "wikidata",
]

CONFIGURATION = Configuration(
    name="Gene Landscape Analysis",
    description="Analyze the landscape of gene nomenclature resources, species-agnostic.",
    inputs=[
        Input(prefix="hgnc", source="pyobo", confidence=0.99),
        Input(prefix="mgi", source="pyobo", confidence=0.99),
        Input(prefix="rgd", source="pyobo", confidence=0.99),
        Input(prefix="cgnc", source="pyobo", confidence=0.99),
        Input(prefix="sgd", source="pyobo", confidence=0.99),
        Input(prefix="civic.gid", source="pyobo", confidence=0.99),
        # Input(prefix="wormbase", source="pyobo", confidence=0.99),
        Input(prefix="flybase", source="pyobo", confidence=0.99),
        Input(prefix="ncit_hgnc", source="custom", confidence=0.99),
        Input(prefix="omim_gene", source="custom", confidence=0.99),
        Input(prefix="wikidata", source="custom", extras=dict(property="P351"), confidence=0.99),  # Entrez
        Input(prefix="wikidata", source="custom", extras=dict(property="P11277"), confidence=0.99),  # CiVIC
        Input(prefix="wikidata", source="custom", extras=dict(property="P594"), confidence=0.99),  # ENSEMBL Gene
        Input(prefix="wikidata", source="custom", extras=dict(property="P354"), confidence=0.99),  # HGNC Gene ID
        Input(prefix="wikidata", source="custom", extras=dict(property="P492"), confidence=0.99),  # OMIM Gene ID
        # Input(prefix="wikidata", source="custom", extras=dict(property="P2892"), confidence=0.99), # UMLS ID
    ],
    add_labels=True,
    priority=PRIORITY,
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
    processed_neo4j_name="semra-gene",
    priority_pickle_path=MODULE.join(name="priority.pkl"),
    priority_sssom_path=MODULE.join(name="priority.sssom.tsv"),
)


@click.command()
def main():
    """Get the gene landscape database."""
    CONFIGURATION.get_mappings(refresh_raw=True, refresh_processed=True)


if __name__ == "__main__":
    main()
