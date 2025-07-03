"""A configuration for assembling mappings for anatomical terms.

The SeMRA Anatomy Mappings Database can be rebuilt with the following commands:

.. code-block:: console

    $ git clone https://github.com/biopragmatics/semra.git
    $ cd semra
    $ uv pip install .[landscape]
    $ python -m semra.landscape.anatomy

The artifacts can be downloaded from `Zenodo
<https://doi.org/10.5281/zenodo.11091802>`_. After running Docker locally, downloading
all files, and unzipping then, the SeMRA web application can be run with:

.. code-block:: console

    $ sh run_on_docker.sh

Navigate to http://localhost:8773 to see the web application.
"""

import pystow

import semra
from semra import Reference
from semra.rules import charlie

__all__ = [
    "ANATOMY_CONFIGURATION",
    "MODULE",
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
    zenodo_record=11091803,
    directory=MODULE.base,
)

if __name__ == "__main__":
    ANATOMY_CONFIGURATION.cli()
