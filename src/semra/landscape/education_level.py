"""Education Level."""

import pystow

from semra import Configuration, Input
from semra.vocabulary import CHARLIE

__all__ = ["EDUCATION_LEVEL_CONFIGURATION"]

KEY = "education-level"
MODULE = pystow.module("semra", "case-studies", KEY)
PREFIXES = [
    "isced1997",
    "isced2011",
    "isced2013",
    "kim.educationlevel",
    "oeh.educationlevel",
    "ans.educationlevel",
]

EDUCATION_LEVEL_CONFIGURATION = Configuration(
    key=KEY,
    name="SeMRA Education Level Mapping Database",
    creators=[CHARLIE],
    inputs=[
        Input(source="biomappings"),
        *(Input(prefix=prefix, source="pyobo", confidence=0.90) for prefix in PREFIXES),
    ],
    priority=PREFIXES,
    add_labels=True,
    remove_imprecise=False,
    directory=MODULE.base,
)

if __name__ == "__main__":
    EDUCATION_LEVEL_CONFIGURATION.cli(copy_to_landscape=True)
