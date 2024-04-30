"""A configuration for assembling mappings for gene terms."""

import click
import pystow

from semra.pipeline import CREATOR_CHARLIE, Configuration, Input, Mutation

__all__ = [
    "MODULE",
    "CONFIGURATION",
]

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
    name="SeMRA Gene Mapping Database",
    description="Analyze the landscape of gene nomenclature resources, species-agnostic.",
    creators=[CREATOR_CHARLIE],
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
        Input(source="wikidata", prefix="ncbigene", confidence=0.99),
        Input(source="wikidata", prefix="civic.gid", confidence=0.99),
        Input(source="wikidata", prefix="ensembl", confidence=0.99),
        Input(source="wikidata", prefix="hgnc", confidence=0.99),
        Input(source="wikidata", prefix="omim", confidence=0.99),
        Input(source="wikidata", prefix="umls", confidence=0.99),
    ],
    subsets={"umls": ["umls:C0017337"], "ncit": ["ncit:C16612"]},
    add_labels=True,
    priority=PRIORITY,
    remove_imprecise=False,
    mutations=[
        Mutation(source="umls", confidence=0.8),
        Mutation(source="ncit", confidence=0.8),
    ],
    raw_pickle_path=MODULE.join(name="raw.pkl.gz"),
    raw_sssom_path=MODULE.join(name="raw.sssom.tsv.gz"),
    # raw_neo4j_path=MODULE.join("neo4j_raw"),
    processed_pickle_path=MODULE.join(name="processed.pkl.gz"),
    processed_sssom_path=MODULE.join(name="processed.sssom.tsv.gz"),
    processed_neo4j_path=MODULE.join("neo4j"),
    processed_neo4j_name="semra-gene",
    priority_pickle_path=MODULE.join(name="priority.pkl.gz"),
    priority_sssom_path=MODULE.join(name="priority.sssom.tsv.gz"),
    configuration_path=MODULE.join(name="configuration.json"),
    zenodo_record=11092012,
)


@click.command()
def main():
    """Build the mapping database for gene terms."""
    CONFIGURATION.get_mappings(refresh_raw=True, refresh_processed=True)
    CONFIGURATION.upload_zenodo()


if __name__ == "__main__":
    main()
