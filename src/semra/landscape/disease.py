"""
The SeMRA Disease Mappings Database assembles semantic mappings to the following
resources:

=======================================================  ================================================================================
Prefix                                                   Name
=======================================================  ================================================================================
`doid <https://bioregistry.io/doid>`_                    Human Disease Ontology
`mondo <https://bioregistry.io/mondo>`_                  Mondo Disease Ontology
`efo <https://bioregistry.io/efo>`_                      Experimental Factor Ontology
`mesh <https://bioregistry.io/mesh>`_                    Medical Subject Headings
`ncit <https://bioregistry.io/ncit>`_                    NCI Thesaurus
`orphanet <https://bioregistry.io/orphanet>`_            Orphanet
`orphanet.ordo <https://bioregistry.io/orphanet.ordo>`_  Orphanet Rare Disease Ontology
`umls <https://bioregistry.io/umls>`_                    Unified Medical Language System Concept Unique Identifier
`omim <https://bioregistry.io/omim>`_                    Online Mendelian Inheritance in Man
`omim.ps <https://bioregistry.io/omim.ps>`_              OMIM Phenotypic Series
`gard <https://bioregistry.io/gard>`_                    Genetic and Rare Diseases Information Center
`icd10 <https://bioregistry.io/icd10>`_                  International Classification of Diseases, 10th Revision
`icd10cm <https://bioregistry.io/icd10cm>`_              International Classification of Diseases, 10th Revision, Clinical Modification
`icd10pcs <https://bioregistry.io/icd10pcs>`_            International Classification of Diseases, 10th Revision, Procedure Coding System
`icd11 <https://bioregistry.io/icd11>`_                  International Classification of Diseases, 11th Revision (Foundation Component)
`icd11.code <https://bioregistry.io/icd11.code>`_        ICD 11 Codes
`icd9 <https://bioregistry.io/icd9>`_                    International Classification of Diseases, 9th Revision
`icd9cm <https://bioregistry.io/icd9cm>`_                International Classification of Diseases, 9th Revision, Clinical Modification
`icdo <https://bioregistry.io/icdo>`_                    International Classification of Diseases for Oncology
=======================================================  ================================================================================

Reproduction
************

The SeMRA Disease Mappings Database can be rebuilt with the following commands:

.. code-block:: console

    $ git clone https://github.com/biopragmatics/semra.git
    $ cd semra
    $ uv pip install .[landscape]
    $ python -m semra.landscape.disease

Web Application
***************
The pre-built artifacts for this mapping database can be downloaded from Zenodo
at |diseaseimg| and unzipped. The web application can be run
locally on Docker from inside the folder where the data was unzipped with:

.. code-block:: console

    $ sh run_on_docker.sh

If you reproduced the database yourself, you can ``cd``
to the right folder and run with:

.. code-block:: console

    $ cd ~/.data/semra/case-studies/disease
    $ sh run_on_docker.sh

Finally, navigate in your web browser to http://localhost:8773 to see the web
application.

.. |diseaseimg| image:: https://zenodo.org/badge/DOI/10.5281/zenodo.11091886.svg
    :target: https://doi.org/10.5281/zenodo.11091886

"""  # noqa:D205,D400


import bioregistry
import pystow

from semra import Reference
from semra.pipeline import Configuration, Input, Mutation
from semra.rules import charlie

__all__ = [
    "DISEASE_CONFIGURATION",
]

ICD_PREFIXES = bioregistry.get_collection("0000004").resources  # type:ignore
MODULE = pystow.module("semra", "case-studies", "disease")
PREFIXES = PRIORITY = [
    "doid",
    "mondo",
    "efo",
    "mesh",
    "ncit",
    "orphanet",
    "orphanet.ordo",
    "umls",
    "omim",
    "omim.ps",
    # "snomedct",
    "gard",
    *ICD_PREFIXES,
]
# some resources are generic, so we want to cut to a relevant subset
SUBSETS = {
    # created with [*get_mesh_category_references("C"), *get_mesh_category_references("F")]
    "mesh": [
        Reference(prefix="mesh", identifier="D007239"),
        Reference(prefix="mesh", identifier="D001520"),
        Reference(prefix="mesh", identifier="D011579"),
        Reference(prefix="mesh", identifier="D001523"),
        Reference(prefix="mesh", identifier="D004191"),
    ],
    "efo": [Reference.from_curie("efo:0000408")],
    "ncit": [Reference.from_curie("ncit:C2991")],
    "umls": [
        # all children of https://uts.nlm.nih.gov/uts/umls/semantic-network/Pathologic%20Function
        Reference.from_curie("sty:T049"),  # cell or molecular dysfunction
        Reference.from_curie("sty:T047"),  # disease or syndrome
        Reference.from_curie("sty:T191"),  # neoplastic process
        Reference.from_curie("sty:T050"),  # experimental model of disease
        Reference.from_curie("sty:T048"),  # mental or behavioral dysfunction
    ],
}

#: Configuration for the disease mappings database
DISEASE_CONFIGURATION = Configuration(
    key="disease",
    name="SeMRA Disease Mappings Database",
    description="Supports the analysis of the landscape of disease nomenclature resources.",
    creators=[charlie],
    inputs=[
        Input(source="biomappings"),
        Input(source="gilda"),
        Input(prefix="doid", source="bioontologies", confidence=0.99),
        Input(prefix="mondo", source="bioontologies", confidence=0.99),
        Input(prefix="efo", source="bioontologies", confidence=0.99),
        Input(prefix="mesh", source="pyobo", confidence=0.99),
        Input(prefix="ncit", source="bioontologies", confidence=0.85),
        Input(prefix="umls", source="pyobo", confidence=0.9),
        Input(prefix="orphanet.ordo", source="bioontologies", confidence=0.9),
        # Input(prefix="orphanet", source="bioontologies", confidence=0.9),
        # Input(prefix="hp", source="bioontologies", confidence=0.99),
    ],
    subsets=SUBSETS,
    add_labels=True,
    priority=PRIORITY,
    keep_prefixes=PREFIXES,
    remove_imprecise=False,
    mutations=[
        Mutation(source="doid", confidence=0.95),
        Mutation(source="mondo", confidence=0.95),
        Mutation(source="efo", confidence=0.90),
        Mutation(source="ncit", confidence=0.7),
        Mutation(source="umls", confidence=0.7),
        Mutation(source="orphanet.ordo", confidence=0.7),
        Mutation(source="orphanet", confidence=0.7),
        # Mutation(source="hp", confidence=0.7),
    ],
    zenodo_record=11091886,
    directory=MODULE.base,
)


if __name__ == "__main__":
    DISEASE_CONFIGURATION.cli()
