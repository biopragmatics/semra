import pystow

from semra import Configuration

KEY = "educationallevel"
PREFIXES = ["isced1997", "isced2011", "isced2013", "kim.educationlevel", "oeh.educationlevel", "ans.educationlevel"]

MODULE = pystow.module("semra", "case-studies", KEY)
CONFIGURATION = Configuration.from_prefixes(
    key=KEY,
    name="Educational Levels",
    prefixes=PREFIXES,
    directory=MODULE.base,
    include_biomappings=False,
    include_gilda=False
)

if __name__ == "__main__":
    CONFIGURATION.cli(copy_to_landscape=True)
