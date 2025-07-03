SeMRA |release| Documentation
=============================

The Semantic Mapping Reasoner and Assembler (SeMRA) is a Python package that provides:

1. An object model for semantic mappings (based on SSSOM)
2. Functionality for assembling and reasoning over semantic mappings at scale
3. A provenance model for automatically generated mappings
4. A confidence model granular at the curator-level, mapping set-level, and community
   feedback-level

Artifacts Overview
------------------

SeMRA was used to produce a comprehensive raw mappings database and five domain-specific mapping databases (each with a landscape analysis).

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
