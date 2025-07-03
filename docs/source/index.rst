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
the digital humanities.

Features
--------

1. An object model for semantic mappings (based on the `Simple Standard for Sharing
   Ontological Mappings (SSSOM) <https://mapping-commons.github.io/sssom/>`_ and
   :mod:`sssom`)
2. Functionality for assembling and reasoning over semantic mappings at scale
3. A provenance model for automatically generated mappings
4. A confidence model granular at the curator-level, mapping set-level, and community
   feedback-level

Artifacts Overview
------------------

SeMRA was used to produce a comprehensive raw mappings database and five domain-specific
mapping databases (each with a landscape analysis).

================== ============================== ================= =========================================================================================================
Domain             Module                         Database Download Analysis
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

The results of the domain-specific landscape analyses can be found on the SeMRA `GitHub
repository <https://github.com/biopragmatics/semra/tree/main/notebooks/landscape>`_

Table of Contents
-----------------

.. toctree::
    :maxdepth: 2
    :caption: Getting Started
    :name: start

    installation
    usage
    cli
    artifacts

Indices and Tables
------------------

- :ref:`genindex`
- :ref:`modindex`
- :ref:`search`
