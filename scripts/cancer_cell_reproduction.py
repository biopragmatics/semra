"""
Reproduce the scenario from the Biomappings paper on cancer cell lines

1. Load positive mappings
   - PyOBO: EFO, DepMap, CCLE
   - Custom: Cellosaurus
   - Biomappings
2. Upgrade mappings from dbxrefs to skos:exactMatch
3. Use transitive closure to infer new mappings
4. Load negative mappings from Biomappings
5. Filter out negative mappings
6. Subset a CCLE->EFO consolidation set
7. Output SSSOM
"""

import click
import pystow

from semra.api import (
    keep_prefixes,
    prioritize,
    process,
    project,
    str_source_target_counts,
    validate_mappings,
)
from semra.io import write_neo4j, write_pickle, write_sssom
from semra.pipeline import Configuration, Input, Mutation, get_raw_mappings

PREFIXES = {
    "efo",
    "cellosaurus",
    "depmap",
    "ccle",
    # "clo", "cl", "bto",
}

MODULE = pystow.module("semra", "case-studies", "cancer-cell-lines")

PRIORITY = ["efo", "cellosaurus", "ccle", "depmap"]

CONFIGURATION = Configuration(
    inputs=[
        Input(source="biomappings"),
        Input(source="gilda"),
        Input(
            source="custom",
            extras={
                "path": "/Users/cthoyt/dev/biomappings/notebooks/cellosaurus_43_xrefs.tsv",
                "source_prefix": "cellosaurus",
                "prefixes": PREFIXES,
                "version": "43",
                "license": "CC-BY-4.0",
            },
        ),
        Input(prefix="efo", source="pyobo", confidence=0.99),
        Input(
            prefix="depmap",
            source="pyobo",
            confidence=0.99,
            extras={"version": "22Q4", "standardize": True, "license": "CC-BY-4.0"},
        ),
        Input(prefix="ccle", source="pyobo", confidence=0.99, extras={"version": "2019"}),
    ],
    priority=PRIORITY,
    mutations=[
        Mutation(source="efo", confidence=0.7),
        Mutation(source="depmap", confidence=0.7),
        Mutation(source="ccle", confidence=0.7),
        Mutation(source="cellosaurus", confidence=0.7),
    ],
)


@click.command()
def main():
    # 1. load mappings
    mappings = get_raw_mappings(CONFIGURATION)
    mappings = keep_prefixes(mappings, PREFIXES)

    validate_mappings(mappings)

    click.echo(f"Loaded {len(mappings):,} positive mappings")
    click.echo(str_source_target_counts(mappings))

    mappings = process(mappings, upgrade_prefixes=PREFIXES, remove_imprecise=False)

    neo4j_path = MODULE.join("neo4j")
    click.echo(f"Output all mappings to {neo4j_path}")
    write_neo4j(mappings, neo4j_path)
    write_sssom(mappings, MODULE.join(name="full.sssom.tsv"))
    write_pickle(mappings, MODULE.join(name="full.pkl"))

    # Produce a consolidation mapping
    for s_prefix, t_prefix in [
        ("ccle", "efo"),
        ("ccle", "depmap"),
    ]:
        consolidation_mappings, sus = project(mappings, s_prefix, t_prefix, return_sus=True)
        click.echo(f"Consolidated to {len(consolidation_mappings):,} mappings between {s_prefix} and {t_prefix}")

        path = MODULE.join(name=f"reproduction_{s_prefix}_{t_prefix}.tsv")
        click.echo(f"Output to {path}")
        write_sssom(consolidation_mappings, path)

        sus_path = MODULE.join(name=f"reproduction_{s_prefix}_{t_prefix}_suspicious.tsv")
        write_sssom(sus, sus_path)

    priority_mapping = prioritize(mappings, PRIORITY)
    click.echo(f"Consolidated to a priority mapping of {len(priority_mapping):,} mappings")

    sssom_path = MODULE.join(name="reproduction_prioritized.tsv")
    click.echo(f"Output to {sssom_path}")
    write_sssom(priority_mapping, sssom_path)

    pickle_path = MODULE.join(name="reproduction_prioritized.pkl")
    click.echo(f"Output to {pickle_path}")
    write_pickle(priority_mapping, pickle_path)


if __name__ == "__main__":
    main()
