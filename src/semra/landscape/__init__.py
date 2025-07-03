"""
The domain-specific processed mapping databases and meta-landscape analysis can be
reconstructed with the following command:

.. code-block:: console

    $ semra landscape
"""

from .anatomy import CONFIGURATION as ANATOMY_CONFIGURATION
from .cells import CONFIGURATION as CELL_CONFIGURATION
from .complexes import CONFIGURATION as COMPLEX_CONFIGURATION
from .diseases import CONFIGURATION as DISEASE_CONFIGURATION
from .genes import CONFIGURATION as GENE_CONFIGURATION

__all__ = [
    "ANATOMY_CONFIGURATION",
    "CELL_CONFIGURATION",
    "COMPLEX_CONFIGURATION",
    "DISEASE_CONFIGURATION",
    "GENE_CONFIGURATION",
]
