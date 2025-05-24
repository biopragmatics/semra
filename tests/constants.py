"""Reusable assets for testing."""

from semra import Reference

a1_curie = "CHEBI:10084"  # Xylopinine
a2_curie = "CHEBI:10100"  # zafirlukast
b1_curie = "mesh:C453820"  # xylopinine
b2_curie = "mesh:C062735"  # zafirlukast
a1, a2 = (
    Reference.from_curie(a1_curie.lower(), name="Xylopinine"),
    Reference.from_curie(a2_curie.lower(), name="zafirlukast"),
)
b1, b2 = (
    Reference.from_curie(b1_curie, name="xylopinine"),
    Reference.from_curie(b2_curie, name="zafirlukast"),
)

TEST_CURIES = {a1, a2, b1, b2}
