"""A configuration for assembling mappings for chemical terms."""

import click
import pystow

from semra.pipeline import Configuration, Input, Mutation

MODULE = pystow.module("semra", "case-studies", "chemical")
PRIORITY = [
    "chebi",
    "pubchem.compound",
    "drugbank",
    "drugcentral",
    "slm",
    "chembl.compound",
]

CONFIGURATION = Configuration(
    name="Chemical Landscape Analysis",
    description="Analyze the landscape of chemicals.",
    inputs=[
        Input(prefix="wikidata", source="custom", extras=dict(prop="P665"), confidence=0.99),
        Input(source="gilda"),
        Input(source="biomappings"),
        Input(prefix="chebi", source="bioontologies", confidence=0.99),
        Input(prefix="slm", source="pyobo", confidence=0.99),
        # Input(prefix="drugbank", source="pyobo", confidence=0.99),
        #
        Input(prefix="chebi", source="wikidata", confidence=0.99),
        Input(prefix="mesh", source="wikidata", confidence=0.99),
        Input(prefix="inchikey", source="wikidata", confidence=0.99),
        Input(prefix="inchi", source="wikidata", confidence=0.99),
        Input(prefix="smiles", source="wikidata", confidence=0.99),
        Input(prefix="cas", source="wikidata", confidence=0.99),
        Input(prefix="chemspider", source="wikidata", confidence=0.99),
        Input(prefix="pubchem.compound", source="wikidata", confidence=0.99),
        Input(prefix="gmelin", source="wikidata", confidence=0.99),
        Input(prefix="chembl.compound", source="wikidata", confidence=0.99),
        Input(prefix="unichem", source="wikidata", confidence=0.99),
        Input(prefix="drugbank", source="wikidata", confidence=0.99),
        Input(prefix="unii", source="wikidata", confidence=0.99),
        Input(prefix="knapsack", source="wikidata", confidence=0.99),
        Input(prefix="hmdb", source="wikidata", confidence=0.99),
        Input(prefix="drugcentral", source="wikidata", confidence=0.99),
        Input(prefix="rxnorm", source="wikidata", confidence=0.99),
        Input(prefix="iuphar.ligand", source="wikidata", confidence=0.99),
        Input(prefix="umbbd.compound", source="wikidata", confidence=0.99),
        Input(prefix="zinc", source="wikidata", confidence=0.99),
        Input(prefix="lipidmaps", source="wikidata", confidence=0.99),
        Input(prefix="slm", source="wikidata", confidence=0.99),
    ],
    add_labels=True,
    priority=PRIORITY,
    remove_imprecise=False,
    mutations=[
        Mutation(source="chebi", confidence=0.95),
    ],
    raw_pickle_path=MODULE.join(name="raw.pkl"),
    raw_sssom_path=MODULE.join(name="raw.sssom.tsv"),
    # raw_neo4j_path=MODULE.join("neo4j_raw"),
    processed_pickle_path=MODULE.join(name="processed.pkl"),
    processed_sssom_path=MODULE.join(name="processed.sssom.tsv"),
    processed_neo4j_path=MODULE.join("neo4j"),
    processed_neo4j_name="semra-chemical",
    priority_pickle_path=MODULE.join(name="priority.pkl"),
    priority_sssom_path=MODULE.join(name="priority.sssom.tsv"),
)


@click.command()
def main():
    """Get the chemical landscape."""
    CONFIGURATION.get_mappings(refresh_raw=True, refresh_processed=True)


if __name__ == "__main__":
    main()
