"""
The SeMRA Protein Complex Mappings Database assembles semantic mappings to the following
resources:

=======================================================  ===================================
Prefix                                                   Name
=======================================================  ===================================
`complexportal <https://bioregistry.io/complexportal>`_  Complex Portal
`fplx <https://bioregistry.io/fplx>`_                    FamPlex
`go <https://bioregistry.io/go>`_                        Gene Ontology
`chembl.target <https://bioregistry.io/chembl.target>`_  ChEMBL target
`wikidata <https://bioregistry.io/wikidata>`_            Wikidata
`scomp <https://bioregistry.io/scomp>`_                  Selventa Complexes
`signor <https://bioregistry.io/signor>`_                Signaling Network Open Resource
`intact <https://bioregistry.io/intact>`_                IntAct protein interaction database
=======================================================  ===================================

Reproduction
************

The SeMRA Protein Complex Mappings Database can be rebuilt with the following commands:

.. code-block:: console

    $ git clone https://github.com/biopragmatics/semra.git
    $ cd semra
    $ uv pip install .[landscape]
    $ python -m semra.landscape.complex

Web Application
***************
The pre-built artifacts for this mapping database can be downloaded from Zenodo
at |compleximg| and unzipped. The web application can be run
locally on Docker from inside the folder where the data was unzipped with:

.. code-block:: console

    $ sh run_on_docker.sh

If you reproduced the database yourself, you can ``cd``
to the right folder and run with:

.. code-block:: console

    $ cd ~/.data/semra/case-studies/complex
    $ sh run_on_docker.sh

Finally, navigate in your web browser to http://localhost:8773 to see the web
application.

.. |compleximg| image:: https://zenodo.org/badge/DOI/10.5281/zenodo.11091422.svg
    :target: https://doi.org/10.5281/zenodo.11091422

"""  # noqa:D205,D400

import pystow

from semra import Reference
from semra.pipeline import Configuration, Input, Mutation
from semra.rules import charlie

__all__ = [
    "COMPLEX_CONFIGURATION",
]

MODULE = pystow.module("semra", "case-studies", "complex")
PREFIXES = PRIORITY = [
    "complexportal",
    "fplx",
    "go",
    "chembl.target",
    "wikidata",
    "scomp",
    # "reactome", # TODO need a subset in Reactome to make this useful
    "signor",
    "intact",
]
SUBSETS = {
    "go": [Reference.from_curie("go:0032991")],
    "chembl.target": [
        Reference(prefix="obo", identifier="chembl.target#protein-complex"),
        Reference(prefix="obo", identifier="chembl.target#protein-complex-group"),
        Reference(prefix="obo", identifier="chembl.target#protein-nucleic-acid-complex"),
    ],
}

#: Configuration for the protein complex mappings database
COMPLEX_CONFIGURATION = Configuration(
    key="complex",
    name="SeMRA Protein Complex Mappings Database",
    description="Analyze the landscape of protein complex nomenclature "
    "resources, species-agnostic.",
    creators=[charlie],
    inputs=[
        Input(source="gilda"),
        Input(source="biomappings"),
        Input(prefix="fplx", source="pyobo", confidence=0.99),
        Input(prefix="fplx", source="custom", confidence=0.99),
        Input(prefix="complexportal", source="pyobo", confidence=0.99),
        Input(prefix="intact", source="pyobo", confidence=0.99),
        Input(prefix="go", source="pyobo", confidence=0.99),
        # Wikidata has mappings as well
        Input(prefix="complexportal", source="wikidata", confidence=0.99),
        Input(prefix="reactome", source="wikidata", confidence=0.99),
    ],
    add_labels=True,
    subsets=SUBSETS,
    priority=PRIORITY,
    post_keep_prefixes=PREFIXES,
    remove_imprecise=False,
    mutations=[
        Mutation(source="go", confidence=0.95),
    ],
    zenodo_record=11091422,
    directory=MODULE.base,
)


if __name__ == "__main__":
    COMPLEX_CONFIGURATION.cli()
