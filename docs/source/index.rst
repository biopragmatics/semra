SeMRA |release| Documentation
=============================

The Semantic Mapping Reasoner and Assembler (SeMRA) is a Python package that provides:

1. An object model for semantic mappings (based on SSSOM)
2. Functionality for assembling and reasoning over semantic mappings at scale
3. A provenance model for automatically generated mappings
4. A confidence model granular at the curator-level, mapping set-level, and community
   feedback-level

SeMRA was used to produce a comprehensive raw mappings database and five domain-specific mapping databases (each with a landscape analysis).

================== ================================ =========================================================== ===================================================================================
Domain             Module                           Database Download                                           Analysis
================== ================================ =========================================================== ===================================================================================
Raw                :mod:`semra.database`            `11082038 <https://bioregistry.io/zenodo.record:11082038>`_ N/A
Disease            :mod:`semra.landscape.disease`   `11091886 <https://bioregistry.io/zenodo.record:11091886>`_ https://github.com/biopragmatics/semra/tree/main/notebooks/landscape/disease#readme
Cell and Cell Line :mod:`semra.landscape.cells`     `11091581 <https://bioregistry.io/zenodo.record:11091581>`_ https://github.com/biopragmatics/semra/tree/main/notebooks/landscape/cell#readme
Anatomy            :mod:`semra.landscape.anatomy`   `11091803 <https://bioregistry.io/zenodo.record:11091803>`_ https://github.com/biopragmatics/semra/tree/main/notebooks/landscape/anatomy#readme
Protein Complex    :mod:`semra.landscape.complexes` `11091422 <https://bioregistry.io/zenodo.record:11091422>`_ https://github.com/biopragmatics/semra/tree/main/notebooks/landscape/complex#readme
Gene               :mod:`semra.landscape.genes`     `11092013 <https://bioregistry.io/zenodo.record:11092013>`_ https://github.com/biopragmatics/semra/tree/main/notebooks/landscape/gene#readme
================== ================================ =========================================================== ===================================================================================

The results of the domain-specific landscape analyses can be found on the SeMRA `GitHub repository
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
