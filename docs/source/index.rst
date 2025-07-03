SeMRA |release| Documentation
=============================

The Semantic Mapping Reasoner and Assembler (SeMRA) assembles semantic mappings to
support data- and knowledge integration across domains. This Python package can be used
by a variety of people:

1. **Data Scientist** - someone who consumes and modifies data to suit an analysis or
   application. For example, they might want to integrate the `Rhea Reaction
   Knowledgebase <https://www.rhea-db.org>`_, which uses `ChEBI
   <https://bioregistry.io/chebi>`_ identifiers for chemicals, and the `Comparative
   Toxicogenomics Database (CTD) <https://ctdbase.org>`_, which uses `MeSH
   <https://bioregistry.io/mesh>`_ identifiers for chemicals. :mod:`semra` assembles
   relevant mappings between ChEBI, MeSH, and other chemical vocabularies and can
   standard both to ChEBI, MeSH, or any other vocabulary.
2. **Curator** - someone who creates data. For example, an ontologist may want to curate
   mapping from entities in their vocabulary to entities in another (or across all
   vocabularies for a domain). SeMRA can assemble mappings and make curation easy via a
   web application.
3. **Data Consumer** - someone who consumes data. This kind of user likely won't
   interact with :mod:`semra` directly, but will likely use tools that build on top of
   it. For example, someone using a knowledge graph or application built on top of use
   this package's assembly, inference, and rewiring functionality indirectly.
4. **Software Developer** - someone who develops tools to support data creators, data
   consumers, and other software developers. For example, a software developer might
   want to make their toolchain more generic for loading, assembling, processing, and
   outputting semantic mappings.

SeMRA is generally applicable in **any domain**, from biomedicine to particle physics to
the digital humanities. Get started by loading external mappings:

.. code-block:: python

    import semra

    mappings = semra.from_sssom(
        # load mappings from any standardized SSSOM file as a file path or URL
        "https://w3id.org/biopragmatics/biomappings/sssom/biomappings.sssom.tsv",
        license="spdx:CC0-1.0",
         mapping_set_title="biomappings",
    )

Or by creating your own mappings:

.. code-block:: python

    from semra import Reference, Mapping, EXACT_MATCH, SimpleEvidence, MappingSet, MANUAL_MAPPING

    r1 = Reference(prefix="chebi", identifier="107635", name="2,3-diacetyloxybenzoic")
    r2 = Reference(prefix="mesh", identifier="C011748", name="tosiben")

    mapping = Mapping(
        subject=r1,
        predicate=EXACT_MATCH,
        object=r2,
        evidence=[
            SimpleEvidence(
                justification=MANUAL_MAPPING,
                confidence=0.99,
                author=Reference(
                    prefix="orcid", identifier="0000-0003-4423-4370", name="Charles Tapley Hoyt"
                ),
                mapping_set=MappingSet(
                    name="biomappings", license="CC0", confidence=0.90,
                ),
            )
        ]
    )

Features
--------

1. An object model for semantic mappings (based on the `Simple Standard for Sharing
   Ontological Mappings (SSSOM) <https://mapping-commons.github.io/sssom/>`_ and
   :mod:`sssom`)
2. Functionality for assembling and reasoning over semantic mappings at scale
3. A provenance model for automatically generated mappings
4. A confidence model granular at the curator-level, mapping set-level, and community
   feedback-level

Here's a conceptual diagram of SeMRA's architecture:

.. image:: img/architecture.svg

What SeMRA Isn't
----------------
SeMRA isn't a tool for predicting semantic mappings like
`Logmap <https://github.com/ernestojimenezruiz/logmap-matcher>`_,
`LOOM <https://www.bioontology.org/wiki/LOOM>`_, or `K-Boom <https://www.biorxiv.org/content/10.1101/048843v3>`_.
Further, it's not a tool for reviewing predicted semantic mappings like
`MapperGPT <https://arxiv.org/abs/2310.03666>`_. However, any of the outputs
from these workflows could be used as inputs to SeMRA's assembly and inference
pipeline.

SeMRA isn't a service that lives on the web, but it does allow you to deploy a local
web application for your use-case specific mapping database.

SeMRA isn't itself a curation tool, but it has the option to integrate :mod:`biomappings`
in deployments of its local web application for curation purposes.

SeMRA isn't an tool for merging ontologies like `CoMerger <https://arxiv.org/abs/2005.02659>`_
or `OntoMerger <https://arxiv.org/abs/2206.02238>`_, but it outputs detailed
and comprehensive semantic mappings that are critical as input for such tools.

Artifacts Overview
------------------

SeMRA was used to produce the `SeMRA Raw Semantic Mappings Database <https://doi.org/10.5281/zenodo.11082038>`_,
a comprehensive raw semantic mappings database, and five domain-specific
mapping databases (each with a landscape analysis). The results of the
domain-specific landscape analyses can be found on the SeMRA `GitHub
repository <https://github.com/biopragmatics/semra/tree/main/notebooks/landscape>`_.

================== ============================== ================= =========================================================================================================
Domain             Docs and Reproduction          Database Download Analysis
================== ============================== ================= =========================================================================================================
Raw                :mod:`semra.database`          |raw|              N/A
Disease            :mod:`semra.landscape.disease` |disease|         `Disease Analysis <https://github.com/biopragmatics/semra/tree/main/notebooks/landscape/disease#readme>`_
Cell and Cell Line :mod:`semra.landscape.cell`    |cell|            `Cell Analysis <https://github.com/biopragmatics/semra/tree/main/notebooks/landscape/cell#readme>`_
Anatomy            :mod:`semra.landscape.anatomy` |anatomy|         `Anatomy Analysis <https://github.com/biopragmatics/semra/tree/main/notebooks/landscape/anatomy#readme>`_
Protein Complex    :mod:`semra.landscape.complex` |complex|         `Complex Analysis <https://github.com/biopragmatics/semra/tree/main/notebooks/landscape/complex#readme>`_
Gene               :mod:`semra.landscape.gene`    |gene|            `Gene Analysis <https://github.com/biopragmatics/semra/tree/main/notebooks/landscape/gene#readme>`_
================== ============================== ================= =========================================================================================================

.. |disease| image:: https://zenodo.org/badge/DOI/10.5281/zenodo.11091885.svg
  :target: https://doi.org/10.5281/zenodo.11091885

.. |cell| image:: https://zenodo.org/badge/DOI/10.5281/zenodo.11091580.svg
  :target: https://doi.org/10.5281/zenodo.11091580

.. |anatomy| image:: https://zenodo.org/badge/DOI/10.5281/zenodo.11091802.svg
  :target: https://doi.org/10.5281/zenodo.11091802

.. |complex| image:: https://zenodo.org/badge/DOI/10.5281/zenodo.11091421.svg
  :target: https://doi.org/10.5281/zenodo.11091421

.. |gene| image:: https://zenodo.org/badge/DOI/10.5281/zenodo.11092012.svg
  :target: https://doi.org/10.5281/zenodo.11092012

.. |raw| image:: https://zenodo.org/badge/DOI/10.5281/zenodo.11082038.svg
  :target: https://doi.org/10.5281/zenodo.11082038


Table of Contents
-----------------

.. toctree::
    :maxdepth: 2
    :caption: Getting Started
    :name: start

    installation
    pipeline
    artifacts
    tutorial
    struct
    io
    reference
    cli

Indices and Tables
------------------

- :ref:`genindex`
- :ref:`modindex`
- :ref:`search`
