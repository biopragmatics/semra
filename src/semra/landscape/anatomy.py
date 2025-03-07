"""A configuration for assembling mappings for anatomical terms."""

import click
import pystow
from curies.vocabulary import charlie
from pyobo.sources.mesh import get_mesh_category_curies

import semra

__all__ = [
    "MODULE",
    "CONFIGURATION",
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
    "mesh": get_mesh_category_curies("A", skip=["A11"]),
    "ncit": ["ncit:C12219"],
    "umls": [
        # see https://uts.nlm.nih.gov/uts/umls/semantic-network/root
        "sty:T024",  # tissue
        "sty:T017",  # anatomical structure
    ],
}

CONFIGURATION = semra.Configuration(
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
    raw_pickle_path=MODULE.join(name="raw.pkl"),
    raw_sssom_path=MODULE.join(name="raw.sssom.tsv"),
    # raw_neo4j_path=MODULE.join("neo4j_raw"),
    processed_pickle_path=MODULE.join(name="processed.pkl"),
    processed_sssom_path=MODULE.join(name="processed.sssom.tsv"),
    processed_neo4j_path=MODULE.join("neo4j"),
    processed_neo4j_name="semra-anatomy",
    priority_pickle_path=MODULE.join(name="priority.pkl"),
    priority_sssom_path=MODULE.join(name="priority.sssom.tsv"),
    configuration_path=MODULE.join(name="configuration.json"),
    zenodo_record=11091803,
)


@click.command()
def main():
    """Build the mapping database for anatomical terms."""
    CONFIGURATION.get_mappings(refresh_raw=True, refresh_processed=True)
    CONFIGURATION.upload_zenodo()


if __name__ == "__main__":
    main()
