"""
The SeMRA Gene Mappings Database assembles semantic mappings to the following
resources:

===============================================  =========================================================
Prefix                                           Name
===============================================  =========================================================
`ncbigene <https://bioregistry.io/ncbigene>`_    NCBI Gene
`hgnc <https://bioregistry.io/hgnc>`_            HUGO Gene Nomenclature Committee
`mgi <https://bioregistry.io/mgi>`_              Mouse Genome Informatics
`rgd <https://bioregistry.io/rgd>`_              Rat Genome Database
`cgnc <https://bioregistry.io/cgnc>`_            Chicken Gene Nomenclature Consortium
`wormbase <https://bioregistry.io/wormbase>`_    WormBase
`flybase <https://bioregistry.io/flybase>`_      FlyBase Gene
`sgd <https://bioregistry.io/sgd>`_              Saccharomyces Genome Database
`omim <https://bioregistry.io/omim>`_            Online Mendelian Inheritance in Man
`civic.gid <https://bioregistry.io/civic.gid>`_  CIViC gene
`umls <https://bioregistry.io/umls>`_            Unified Medical Language System Concept Unique Identifier
`ncit <https://bioregistry.io/ncit>`_            NCI Thesaurus
`wikidata <https://bioregistry.io/wikidata>`_    Wikidata
===============================================  =========================================================

Reproduction
************

The SeMRA Gene Mappings Database can be rebuilt with the following commands:

.. code-block:: console

    $ git clone https://github.com/biopragmatics/semra.git
    $ cd semra
    $ uv pip install .[landscape]
    $ python -m semra.landscape.gene

Web Application
***************
The pre-built artifacts for this mapping database can be downloaded from Zenodo
at |gene| and unzipped. The web application can be run
locally on Docker from inside the folder where the data was unzipped with:

.. code-block:: console

    $ sh run_on_docker.sh

If you reproduced the database yourself, you can ``cd``
to the right folder and run with:

.. code-block:: console

    $ cd ~/.data/semra/case-studies/gene
    $ sh run_on_docker.sh

Finally, navigate in your web browser to http://localhost:8773 to see the web
application.

.. |gene| image:: https://zenodo.org/badge/DOI/10.5281/zenodo.11092013.svg
    :target: https://doi.org/10.5281/zenodo.11092013

"""  # noqa:D205,D400

import pystow

from semra import Reference
from semra.pipeline import Configuration, Input, Mutation
from semra.rules import charlie

__all__ = [
    "GENE_CONFIGURATION",
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

#: Configuration for the gene mappings database
GENE_CONFIGURATION = Configuration(
    key="gene",
    name="SeMRA Gene Mappings Database",
    description="Analyze the landscape of gene nomenclature resources, species-agnostic.",
    creators=[charlie],
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
    subsets={
        "umls": [Reference.from_curie("umls:C0017337")],
        "ncit": [Reference.from_curie("ncit:C16612")],
    },
    add_labels=True,
    priority=PRIORITY,
    remove_imprecise=False,
    mutations=[
        Mutation(source="umls", confidence=0.8),
        Mutation(source="ncit", confidence=0.8),
    ],
    zenodo_record=11092013,
    directory=MODULE.base,
)


if __name__ == "__main__":
    GENE_CONFIGURATION.cli()
