"""Tests for landscape configuration."""

from unittest import TestCase

from semra.landscape import CONFIGURATIONS
from semra.pipeline import assert_bioregistry_canonical


class TestLandscapeConfiguration(TestCase):
    """Tests for landscape configuration."""

    def test_prefixes(self) -> None:
        """Test prefixes are standard."""
        for configuration in CONFIGURATIONS:
            with self.subTest(configuration=configuration.key):
                for inp in configuration.inputs:
                    if inp.source in {"pyobo", "wikidata", "bioontologies"} and inp.prefix:
                        assert_bioregistry_canonical(inp.prefix)
                for mutation in configuration.mutations or []:
                    assert_bioregistry_canonical(mutation.source)
                    if isinstance(mutation.target, str):
                        assert_bioregistry_canonical(mutation.target)
                    elif isinstance(mutation.target, list):
                        for prefix in mutation.target:
                            assert_bioregistry_canonical(prefix)
                for prefix in configuration.priority:
                    assert_bioregistry_canonical(prefix)
                for prefix in configuration.subsets or {}:
                    assert_bioregistry_canonical(prefix)
