"""
The SeMRA Taxonomical Ranks Mappings Database assembles semantic mappings to the following
resources:

=========================================================  =============================
Prefix                                                     Name
=========================================================  =============================
`taxrank <https://bioregistry.io/taxrank>`_                Taxonomic rank vocabulary
`ncbitaxon <https://bioregistry.io/ncbitaxon>`_            NCBI Taxonomy
`tdwg.taxonrank <https://bioregistry.io/tdwg.taxonrank>`_  TDWG Taxon Rank LSID Ontology
=========================================================  =============================

Results
*******
The SeMRA Taxonomical Ranks Mappings Database is available for download as SSSOM, JSON, and
in a format ready for loading into a Neo4j graph database
on Zenodo at |taxrankimg|.

A summary of the results can be viewed on the SeMRA GitHub repository in the
`notebooks/landscape/taxrank <https://github.com/biopragmatics/semra/tree/main/notebooks/landscape/taxrank#readme>`_
folder.

Reproduction
************

The SeMRA Taxonomical Ranks Mappings Database can be rebuilt with the following commands:

.. code-block:: console

    $ git clone https://github.com/biopragmatics/semra.git
    $ cd semra
    $ uv pip install .[landscape]
    $ python -m semra.landscape.taxrank

.. note::

    Downloading raw data resources can take on the order of hours to tens
    of hours depending on your internet connection and the reliability of
    the resources' respective servers.

    Processing and analysis can be run overnight on commodity hardware
    (e.g., a 2023 MacBook Pro with 36GB RAM).

Web Application
***************
After building the database, the web application can be run locally on Docker
with the following commands:

.. code-block:: console

    $ cd ~/.data/semra/case-studies/taxrank
    $ sh run_on_docker.sh

Finally, navigate in your web browser to http://localhost:8773 to see the web
application.

.. |taxrankimg| image:: https://zenodo.org/badge/DOI/10.5281/zenodo.None.svg
    :target: https://doi.org/10.5281/zenodo.None

"""  # noqa:D205,D400

import pystow

import semra
from semra.rules import charlie

__all__ = [
    "TAXRANK_CONFIGURATION",
]

MODULE = pystow.module("semra", "case-studies", "taxranks")
PRIORITY = [
    "taxrank",
    "ncbitaxon",
    "tdwg.taxonrank",
]
SUBSETS = {"ncbitaxon": [semra.Reference(prefix="ncbitaxon", identifier="taxonomic_rank")]}

TAXRANK_CONFIGURATION = semra.Configuration(
    key="taxrank",
    name="SeMRA Taxonomical Ranks Mappings Database",
    description="Supports the analysis of the landscape of taxnomical rank nomenclature resources.",
    creators=[charlie],
    inputs=[
        semra.Input(prefix="taxrank", source="pyobo", confidence=0.99),
    ],
    subsets=SUBSETS,
    add_labels=False,
    priority=PRIORITY,
    remove_imprecise=False,
    mutations=[
        semra.Mutation(source="taxrank", confidence=0.99),
    ],
    directory=MODULE.base,
)

if __name__ == "__main__":
    TAXRANK_CONFIGURATION.cli()
