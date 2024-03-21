"""Disease Landscape Assessment."""

import click
import pystow

from semra.pipeline import Configuration, Input, Mutation

MODULE = pystow.module("semra", "case-studies", "disease")
PREFIXES = PRIORITY = ["doid", "mondo", "efo", "mesh", "ncit", "hp"]

CONFIGURATION = Configuration(
    name="Disease Landscape Analysis",
    description="",
    inputs=[
        Input(source="biomappings"),
        Input(source="gilda"),
        Input(prefix="doid", source="bioontologies", confidence=0.99),
        Input(prefix="mondo", source="bioontologies", confidence=0.99),
        Input(prefix="efo", source="bioontologies", confidence=0.99),
        Input(prefix="mesh", source="pyobo", confidence=0.99),
        Input(prefix="ncit", source="bioontologies", confidence=0.85),
        # Input(prefix="hp", source="bioontologies", confidence=0.99),
    ],
    add_labels=True,
    priority=PRIORITY,
    keep_prefixes=PREFIXES,
    remove_imprecise=False,
    mutations=[
        Mutation(source="doid", confidence=0.95),
        Mutation(source="mondo", confidence=0.95),
        Mutation(source="efo", confidence=0.90),
        Mutation(source="ncit", confidence=0.7),
        # Mutation(source="hp", confidence=0.7),
    ],
    # NEO4j options - add ontologies
    raw_pickle_path=MODULE.join(name="raw.pkl"),
    raw_sssom_path=MODULE.join(name="raw.sssom.tsv"),
    raw_neo4j_path=MODULE.join("neo4j_raw"),
    processed_pickle_path=MODULE.join(name="processed.pkl"),
    processed_sssom_path=MODULE.join(name="processed.sssom.tsv"),
    processed_neo4j_path=MODULE.join("neo4j"),
    processed_neo4j_name="semra-disease",
    priority_pickle_path=MODULE.join(name="priority.pkl"),
    priority_sssom_path=MODULE.join(name="priority.sssom.tsv"),
)


@click.command()
def main():
    """Get the disease landscape database."""
    CONFIGURATION.get_mappings(refresh_raw=False, refresh_processed=False)


if __name__ == "__main__":
    main()
