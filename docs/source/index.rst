SeMRA |release| Documentation
=============================

The Semantic Mapping Reasoner and Assembler (SeMRA) is a Python package that provides:

1. An object model for semantic mappings (based on SSSOM)
2. Functionality for assembling and reasoning over semantic mappings at scale
3. A provenance model for automatically generated mappings
4. A confidence model granular at the curator-level, mapping set-level, and community
   feedback-level

We produced five domain-specific mapping analyses, each with a reusable database.

================== ================================ =============================================
Domain             Module                           Data Download
================== ================================ =============================================
Raw
Disease            :mod:`semra.landscape.disease`   https://bioregistry.io/zenodo.record:11091886
Cell and Cell Line :mod:`semra.landscape.cells`     https://bioregistry.io/zenodo.record:11091581
Anatomy            :mod:`semra.landscape.anatomy`   https://bioregistry.io/zenodo.record:11091803
Protein Complex    :mod:`semra.landscape.complexes` https://bioregistry.io/zenodo.record:11091422
Gene               :mod:`semra.landscape.genes`     https://bioregistry.io/zenodo.record:11092013
================== ================================ =============================================

More information can be found on the SeMRA `GitHub repository
<https://github.com/biopragmatics/semra/tree/main/notebooks/landscape>`_

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
