"""Tests for utilities."""

import unittest

from semra.utils import format_number, get_orcid_name


class TestUtils(unittest.TestCase):
    """Tests for utilities."""

    def test_get_orcid_name(self) -> None:
        """Test getting ORCiD name."""
        for name, orcid in [
            ("Charles Tapley Hoyt", "orcid:0000-0003-4423-4370"),
            ("Charles Tapley Hoyt", "0000-0003-4423-4370"),
            ("Charles Tapley Hoyt", "https://orcid.org/0000-0003-4423-4370"),
            (None, "xx"),
        ]:
            self.assertEqual(name, get_orcid_name(orcid))

    def test_format_number(self) -> None:
        """Test formatting a number."""
        for number, abbreviation, suffix in [
            (1, 1, ""),
            (10, 10, ""),
            (100, 100, ""),
            (1_000, 1, "K"),
            (1_001, 1, "K"),
            (1_010, 1, "K"),
            (1_100, 1.1, "K"),
            (10_000, 10, "K"),
            (10_001, 10, "K"),
            (10_010, 10, "K"),
            (10_100, 10, "K"),
            (11_000, 11, "K"),
            (100_000, 100, "K"),
            (100_100, 100, "K"),
            (1_000_000, 1, "M"),
            (1_000_100, 1, "M"),
            (1_010_000, 1, "M"),
            (1_100_000, 1.1, "M"),
        ]:
            with self.subTest(number=number):
                self.assertEqual((abbreviation, suffix), format_number(number), msg=f"for {number}")
