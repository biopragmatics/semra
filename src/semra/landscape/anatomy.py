"""
The SeMRA Anatomy Mappings Database assembles semantic mappings to the following
resources:

=========================================  =========================================================
Prefix                                     Name
=========================================  =========================================================
`uberon <https://bioregistry.io/uberon>`_  Uber Anatomy Ontology
`mesh <https://bioregistry.io/mesh>`_      Medical Subject Headings
`bto <https://bioregistry.io/bto>`_        BRENDA Tissue Ontology
`caro <https://bioregistry.io/caro>`_      Common Anatomy Reference Ontology
`ncit <https://bioregistry.io/ncit>`_      NCI Thesaurus
`umls <https://bioregistry.io/umls>`_      Unified Medical Language System Concept Unique Identifier
=========================================  =========================================================

Results
*******
The SeMRA Anatomy Mappings Database is available for download as SSSOM, JSON, and
in a format ready for loading into a Neo4j graph database
on Zenodo at |anatomyimg|.

A summary of the results can be viewed on the SeMRA GitHub repository in the
`notebooks/landscape/anatomy <https://github.com/biopragmatics/semra/tree/main/notebooks/landscape/anatomy#readme>`_
folder.

Reproduction
************

The SeMRA Anatomy Mappings Database can be rebuilt with the following commands:

.. code-block:: console

    $ git clone https://github.com/biopragmatics/semra.git
    $ cd semra
    $ uv pip install .[landscape]
    $ python -m semra.landscape.anatomy

.. note::

    Downloading raw data resources can take on the order of hours to tens
    of hours depending on your internet connection and the reliability of
    the resources' respective servers.

    Processing and analysis can be run overnight on commodity hardware
    (e.g., a 2023 MacBook Pro with 36GB RAM).

Web Application
***************
The pre-built artifacts for this mapping database can be downloaded from Zenodo
at |anatomyimg| and unzipped. The web application can be run
locally on Docker from inside the folder where the data was unzipped with:

.. code-block:: console

    $ sh run_on_docker.sh

If you reproduced the database yourself, you can ``cd``
to the right folder and run with:

.. code-block:: console

    $ cd ~/.data/semra/case-studies/anatomy
    $ sh run_on_docker.sh

Finally, navigate in your web browser to http://localhost:8773 to see the web
application.

.. |anatomyimg| image:: https://zenodo.org/badge/DOI/10.5281/zenodo.11091802.svg
    :target: https://doi.org/10.5281/zenodo.11091802

"""  # noqa:D205,D400

import pystow

import semra
from semra import Reference
from semra.vocabulary import CHARLIE

__all__ = [
    "ANATOMY_CONFIGURATION",
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
    # this mesh list is created with a call to pyobo.sources.mesh.get_mesh_category_references("A", skip=["A11"])
    "mesh": [
        Reference(prefix="mesh", identifier="D001829"),
        Reference(prefix="mesh", identifier="D009141"),
        Reference(prefix="mesh", identifier="D004064"),
        Reference(prefix="mesh", identifier="D012137"),
        Reference(prefix="mesh", identifier="D014566"),
        Reference(prefix="mesh", identifier="D004703"),
        Reference(prefix="mesh", identifier="D002319"),
        Reference(prefix="mesh", identifier="D009420"),
        Reference(prefix="mesh", identifier="D012679"),
        Reference(prefix="mesh", identifier="D014024"),
        Reference(prefix="mesh", identifier="D005441"),
        Reference(prefix="mesh", identifier="D000825"),
        Reference(prefix="mesh", identifier="D013284"),
        Reference(prefix="mesh", identifier="D006424"),
        Reference(prefix="mesh", identifier="D004628"),
        Reference(prefix="mesh", identifier="D034582"),
        Reference(prefix="mesh", identifier="D018514"),
        Reference(prefix="mesh", identifier="D056229"),
        Reference(prefix="mesh", identifier="D056226"),
        Reference(prefix="mesh", identifier="D056224"),
    ],
    "ncit": [Reference.from_curie("ncit:C12219")],
    "umls": [
        # see https://uts.nlm.nih.gov/uts/umls/semantic-network/root
        Reference.from_curie("sty:T024"),  # tissue
        Reference.from_curie("sty:T017"),  # anatomical structure
    ],
}

#: Configuration for the anatomy mappings database
ANATOMY_CONFIGURATION = semra.Configuration(
    key="anatomy",
    name="SeMRA Anatomy Mappings Database",
    description="Supports the analysis of the landscape of anatomy nomenclature resources.",
    creators=[CHARLIE],
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
    zenodo_record=11091802,
    directory=MODULE.base,
)

if __name__ == "__main__":
    ANATOMY_CONFIGURATION.cli(copy_to_landscape=True)
