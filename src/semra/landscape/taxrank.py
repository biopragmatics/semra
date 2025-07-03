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

Reproduction
************

The SeMRA Taxonomical Ranks Mappings Database can be rebuilt with the following commands:

.. code-block:: console

    $ git clone https://github.com/biopragmatics/semra.git
    $ cd semra
    $ uv pip install .[landscape]
    $ python -m semra.landscape.taxrank

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
