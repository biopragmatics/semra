"""Instrument."""

import pystow
from pydantic import AnyUrl
from sssom_pydantic import MappingSet

from semra.pipeline import Configuration, Input
from semra.vocabulary import CHARLIE

__all__ = [
    "INSTRUMENT_CONFIGURATION",
]

KEY = "instrument"
MODULE = pystow.module("semra", "case-studies", KEY)
PREFIXES = PRIORITY = [
    "chmo",
    "fbbi",
    "panet",
    "goldbook",
    "fix",
    "rex",
]

#: Configuration for the instrument mappings database
INSTRUMENT_CONFIGURATION = Configuration(
    key=KEY,
    name="SeMRA Instrument Mappings Database",
    description="Analyze the landscape of instrument nomenclature resources, species-agnostic.",
    creators=[CHARLIE],
    inputs=[
        Input(source="biomappings"),
        Input(
            source="sssom",
            prefix="https://github.com/nfdi-de/section-metadata-wg-onto/raw/refs/heads/main/sssom/data/positive.sssom.tsv",
            extras={
                "metadata": MappingSet(
                    id=AnyUrl(
                        "https://github.com/nfdi-de/section-metadata-wg-onto/raw/refs/heads/main/sssom/data/positive.sssom.tsv"
                    ),
                    source=[AnyUrl("https://wikidata.org/wiki/Q139055838")],
                )
            },
        ),
        Input(prefix="chmo", source="pyobo", confidence=0.99),
        Input(prefix="panet", source="pyobo", confidence=0.99),
        Input(prefix="fbbi", source="pyobo", confidence=0.99),
        Input(prefix="fix", source="pyobo", confidence=0.99),
        Input(prefix="rex", source="pyobo", confidence=0.99),
        Input(prefix="goldbook", source="pyobo", confidence=0.99),
    ],
    add_labels=True,
    priority=PRIORITY,
    post_keep_prefixes=PREFIXES,
    remove_imprecise=False,
    directory=MODULE.base,
)

if __name__ == "__main__":
    INSTRUMENT_CONFIGURATION.cli(copy_to_landscape=True)
