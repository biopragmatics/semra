"""Tests for I/O functions."""

import getpass
import unittest

from semra.io import from_pyobo

LOCAL = getpass.getuser() == "cthoyt"


@unittest.skipUnless(LOCAL, reason="Don't test remotely since PyOBO content isn't available")
class TestIO(unittest.TestCase):
    """Test I/O functions."""

    def test_from_pyobo(self):
        """Test loading content from PyOBO."""
        mappings = from_pyobo("doid")
        for mapping in mappings:
            self.assertEquals("doid", mapping.s.prefix)

        mappings_2 = from_pyobo("doid", "mesh")
        for mapping in mappings_2:
            self.assertEquals("doid", mapping.s.prefix)
            self.assertEquals("mesh", mapping.o.prefix)
