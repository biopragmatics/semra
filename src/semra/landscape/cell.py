"""
The SeMRA Cell and Cell Line Mappings Database assembles semantic mappings to the following
resources:

===================================================  =========================================================
Prefix                                               Name
===================================================  =========================================================
`mesh <https://bioregistry.io/mesh>`_                Medical Subject Headings
`efo <https://bioregistry.io/efo>`_                  Experimental Factor Ontology
`cellosaurus <https://bioregistry.io/cellosaurus>`_  Cellosaurus
`ccle <https://bioregistry.io/ccle>`_                Cancer Cell Line Encyclopedia Cells
`depmap <https://bioregistry.io/depmap>`_            DepMap Cell Lines
`bto <https://bioregistry.io/bto>`_                  BRENDA Tissue Ontology
`cl <https://bioregistry.io/cl>`_                    Cell Ontology
`clo <https://bioregistry.io/clo>`_                  Cell Line Ontology
`ncit <https://bioregistry.io/ncit>`_                NCI Thesaurus
`umls <https://bioregistry.io/umls>`_                Unified Medical Language System Concept Unique Identifier
===================================================  =========================================================

Results
*******
The SeMRA Cell and Cell Line Mappings Database is available for download as SSSOM, JSON, and
in a format ready for loading into a Neo4j graph database
on Zenodo at |cellimg|.

A summary of the results can be viewed on the SeMRA GitHub repository in the
`notebooks/landscape/cell <https://github.com/biopragmatics/semra/tree/main/notebooks/landscape/cell#readme>`_
folder.

Reproduction
************

The SeMRA Cell and Cell Line Mappings Database can be rebuilt with the following commands:

.. code-block:: console

    $ git clone https://github.com/biopragmatics/semra.git
    $ cd semra
    $ uv pip install .[landscape]
    $ python -m semra.landscape.cell

.. note::

    Downloading raw data resources can take on the order of hours to tens
    of hours depending on your internet connection and the reliability of
    the resources' respective servers.

    Processing and analysis can be run overnight on commodity hardware
    (e.g., a 2023 MacBook Pro with 36GB RAM).

Web Application
***************
The pre-built artifacts for this mapping database can be downloaded from Zenodo
at |cellimg| and unzipped. The web application can be run
locally on Docker from inside the folder where the data was unzipped with:

.. code-block:: console

    $ sh run_on_docker.sh

If you reproduced the database yourself, you can ``cd``
to the right folder and run with:

.. code-block:: console

    $ cd ~/.data/semra/case-studies/cell
    $ sh run_on_docker.sh

Finally, navigate in your web browser to http://localhost:8773 to see the web
application.

.. |cellimg| image:: https://zenodo.org/badge/DOI/10.5281/zenodo.11091580.svg
    :target: https://doi.org/10.5281/zenodo.11091580

"""  # noqa:D205,D400

import click
import pystow

from semra import Reference
from semra.api import project
from semra.io import write_sssom
from semra.pipeline import Configuration, Input, MappingPack, Mutation
from semra.vocabulary import CHARLIE

__all__ = [
    "CELL_CONFIGURATION",
]

MODULE = pystow.module("semra", "case-studies", "cells")
PREFIXES = PRIORITY = [
    "mesh",
    "efo",
    "cellosaurus",
    "ccle",
    "depmap",
    "bto",
    "cl",
    "clo",
    "ncit",
    "umls",
]

# some resources are generic, so we want to cut to a relevant subset
SUBSETS = {
    "mesh": [Reference.from_curie("mesh:D002477")],
    "efo": [Reference.from_curie("efo:0000324")],
    "ncit": [Reference.from_curie("ncit:C12508")],
    "umls": [
        Reference.from_curie("sty:T025")
    ],  # see https://uts.nlm.nih.gov/uts/umls/semantic-network/root
}

#: Configuration for the cell and cell type mappings database
CELL_CONFIGURATION = Configuration(
    key="cell",
    name="SeMRA Cell and Cell Line Mappings Database",
    description="Originally a reproduction of the EFO/Cellosaurus/DepMap/CCLE scenario posed in "
    "the Biomappings paper, this configuration imports several different cell and cell line "
    "resources and identifies mappings between them.",
    creators=[CHARLIE],
    inputs=[
        Input(source="biomappings"),
        Input(source="gilda"),
        Input(prefix="cellosaurus", source="pyobo", confidence=0.99),
        Input(prefix="bto", source="bioontologies", confidence=0.99),
        Input(prefix="cl", source="bioontologies", confidence=0.99),
        Input(prefix="clo", source="custom", confidence=0.65),
        Input(prefix="efo", source="pyobo", confidence=0.99),
        Input(
            prefix="depmap",
            source="pyobo",
            confidence=0.99,
            extras={"version": "22Q4", "standardize": True, "license": "CC-BY-4.0"},
        ),
        Input(prefix="ccle", source="pyobo", confidence=0.99, extras={"version": "2019"}),
        Input(prefix="ncit", source="pyobo", confidence=0.99),
        Input(prefix="umls", source="pyobo", confidence=0.99),
    ],
    subsets=SUBSETS,
    priority=PRIORITY,
    keep_prefixes=PREFIXES,
    remove_imprecise=False,
    mutations=[
        Mutation(source="efo", confidence=0.7),
        Mutation(source="bto", confidence=0.7),
        Mutation(source="cl", confidence=0.7),
        Mutation(source="clo", confidence=0.7),
        Mutation(source="depmap", confidence=0.7),
        Mutation(source="ccle", confidence=0.7),
        Mutation(source="cellosaurus", confidence=0.7),
        Mutation(source="ncit", confidence=0.7),
        Mutation(source="umls", confidence=0.7),
    ],
    add_labels=True,
    zenodo_record=11091580,
    directory=MODULE.base,
)


def cell_consolidation_hook(config: Configuration, pack: MappingPack) -> None:
    """Write consolidation mappings from CCLE to EFO and DepMap."""
    # Produce consolidation mappings
    for s_prefix, t_prefix in [
        ("ccle", "efo"),
        ("ccle", "depmap"),
    ]:
        consolidation_mappings, sus = project(pack.processed, s_prefix, t_prefix, return_sus=True)
        click.echo(
            f"Consolidated to {len(consolidation_mappings):,} mappings between "
            f"{s_prefix} and {t_prefix}"
        )

        path = MODULE.join(name=f"reproduction_{s_prefix}_{t_prefix}.tsv")
        click.echo(f"Output to {path}")
        write_sssom(consolidation_mappings, path)

        sus_path = MODULE.join(name=f"reproduction_{s_prefix}_{t_prefix}_suspicious.tsv")
        write_sssom(sus, sus_path)


if __name__ == "__main__":
    CELL_CONFIGURATION.cli(hooks=[cell_consolidation_hook])
