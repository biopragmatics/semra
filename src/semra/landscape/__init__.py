"""
The domain-specific processed mapping databases and meta-landscape analysis can be
reconstructed with the following commands:

.. code-block:: console

    $ git clone https://github.com/biopragmatics/semra.git
    $ cd semra
    $ uv pip install .[landscape]
    $ semra landscape

The ``semra landscape`` command runs all pre-configured domain-specific mapping
database construction, landscape analyses, and the meta-landscape analysis.

.. note::

    Downloading raw data resources can take on the order of hours to tens
    of hours depending on your internet connection and the reliability of
    the resources' respective servers.

    Processing and analysis can be run overnight on commodity hardware
    (e.g., a 2023 MacBook Pro with 36GB RAM).

The results can be found here:

================== ============================== ================= =========================================================================================================
Domain             Module                         Database Download Analysis
================== ============================== ================= =========================================================================================================
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

"""  # noqa:D205,D400

from .anatomy import ANATOMY_CONFIGURATION
from .cell import CELL_CONFIGURATION
from .complex import COMPLEX_CONFIGURATION
from .disease import DISEASE_CONFIGURATION
from .gene import GENE_CONFIGURATION
from .taxrank import TAXRANK_CONFIGURATION

__all__ = [
    "ANATOMY_CONFIGURATION",
    "CELL_CONFIGURATION",
    "COMPLEX_CONFIGURATION",
    "DISEASE_CONFIGURATION",
    "GENE_CONFIGURATION",
    "TAXRANK_CONFIGURATION",
]
