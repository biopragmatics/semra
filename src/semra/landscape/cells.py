"""A configuration for assembling mappings for cell and cell line terms.

This configuration can be used to reproduce the results from the Biomappings paper by
doing the following:

1. Load positive mappings - PyOBO: EFO, DepMap, CCLE - Custom: Cellosaurus - Biomappings
2. Upgrade mappings from dbxrefs to skos:exactMatch
3. Use transitive closure to infer new mappings
4. Load negative mappings from Biomappings
5. Filter out negative mappings
6. Subset a CCLE->EFO consolidation set
7. Output SSSOM
"""

import click
import pystow

from semra import Reference
from semra.api import project, str_source_target_counts
from semra.io import write_sssom
from semra.pipeline import (
    BUILD_DOCKER_OPTION,
    REFRESH_PROCESSED_OPTION,
    REFRESH_RAW_OPTION,
    REFRESH_SOURCE_OPTION,
    UPLOAD_OPTION,
    Configuration,
    Input,
    Mutation,
    get_priority_mappings_from_config,
)
from semra.rules import charlie

__all__ = [
    "CONFIGURATION",
    "MODULE",
]

MODULE = pystow.module("semra", "case-studies", "cells")
PREFIXES = PRIORITY = [
    "mesh",
    "efo",
    "cellosaurus",
    "ccle",
    "depmap",
    "bto",
    "cl",
    "clo",
    "ncit",
    "umls",
]

# some resources are generic, so we want to cut to a relevant subset
SUBSETS = {
    "mesh": [Reference.from_curie("mesh:D002477")],
    "efo": [Reference.from_curie("efo:0000324")],
    "ncit": [Reference.from_curie("ncit:C12508")],
    "umls": [
        Reference.from_curie("sty:T025")
    ],  # see https://uts.nlm.nih.gov/uts/umls/semantic-network/root
}

CONFIGURATION = Configuration(
    key="cell",
    name="SeMRA Cell and Cell Line Mappings Database",
    description="Originally a reproduction of the EFO/Cellosaurus/DepMap/CCLE scenario posed in "
    "the Biomappings paper, this configuration imports several different cell and cell line "
    "resources and identifies mappings between them.",
    creators=[charlie],
    inputs=[
        Input(source="biomappings"),
        Input(source="gilda"),
        Input(prefix="cellosaurus", source="pyobo", confidence=0.99),
        Input(prefix="bto", source="bioontologies", confidence=0.99),
        Input(prefix="cl", source="bioontologies", confidence=0.99),
        Input(prefix="clo", source="custom", confidence=0.65),
        Input(prefix="efo", source="pyobo", confidence=0.99),
        Input(
            prefix="depmap",
            source="pyobo",
            confidence=0.99,
            extras={"version": "22Q4", "standardize": True, "license": "CC-BY-4.0"},
        ),
        Input(prefix="ccle", source="pyobo", confidence=0.99, extras={"version": "2019"}),
        Input(prefix="ncit", source="pyobo", confidence=0.99),
        Input(prefix="umls", source="pyobo", confidence=0.99),
    ],
    subsets=SUBSETS,
    priority=PRIORITY,
    keep_prefixes=PREFIXES,
    remove_imprecise=False,
    mutations=[
        Mutation(source="efo", confidence=0.7),
        Mutation(source="bto", confidence=0.7),
        Mutation(source="cl", confidence=0.7),
        Mutation(source="clo", confidence=0.7),
        Mutation(source="depmap", confidence=0.7),
        Mutation(source="ccle", confidence=0.7),
        Mutation(source="cellosaurus", confidence=0.7),
        Mutation(source="ncit", confidence=0.7),
        Mutation(source="umls", confidence=0.7),
    ],
    add_labels=True,
    zenodo_record=11091581,
    directory=MODULE.base,
)


@click.command()
@UPLOAD_OPTION
@REFRESH_RAW_OPTION
@REFRESH_PROCESSED_OPTION
@REFRESH_SOURCE_OPTION
@BUILD_DOCKER_OPTION
def main(
    upload: bool,
    refresh_source: bool,
    refresh_raw: bool,
    refresh_processed: bool,
    build_docker: bool,
) -> None:
    """Build the mapping database for cell and cell line terms."""
    priority_mappings = get_priority_mappings_from_config(
        CONFIGURATION,
        refresh_raw=refresh_raw,
        refresh_processed=refresh_processed,
        refresh_source=refresh_source,
    )
    if build_docker and CONFIGURATION.processed_neo4j_path:
        CONFIGURATION._build_docker()
    if upload:
        CONFIGURATION._safe_upload()

    click.echo(f"Processing returned {len(priority_mappings):,} prioritized mappings")
    click.echo(str_source_target_counts(priority_mappings))

    # Produce consolidation mappings
    for s_prefix, t_prefix in [
        ("ccle", "efo"),
        ("ccle", "depmap"),
    ]:
        consolidation_mappings, sus = project(
            priority_mappings, s_prefix, t_prefix, return_sus=True
        )
        click.echo(
            f"Consolidated to {len(consolidation_mappings):,} mappings between "
            f"{s_prefix} and {t_prefix}"
        )

        path = MODULE.join(name=f"reproduction_{s_prefix}_{t_prefix}.tsv")
        click.echo(f"Output to {path}")
        write_sssom(consolidation_mappings, path)

        sus_path = MODULE.join(name=f"reproduction_{s_prefix}_{t_prefix}_suspicious.tsv")
        write_sssom(sus, sus_path)


if __name__ == "__main__":
    main()
