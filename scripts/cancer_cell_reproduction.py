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

import biomappings
import click
import pystow

from semra.api import (
    filter_prefixes,
    prioritize,
    process,
    project,
    str_source_target_counts,
    validate_mappings,
)
from semra.io import from_biomappings, from_cache_df, from_pyobo, write_neo4j, write_pickle, write_sssom
from semra.sources.gilda import from_gilda

PREFIXES = {
    "efo",
    "cellosaurus",
    "depmap",
    "ccle",
    # "clo", "cl", "bto",
}

MODULE = pystow.module("semra", "case-studies", "cancer-cell-lines")


@click.command()
def main():
    # 1. load mappings
    mappings = []
    mappings.extend(from_pyobo("efo"))
    mappings.extend(from_pyobo("depmap", version="22Q4", standardize=True))
    mappings.extend(from_pyobo("ccle", version="2019"))
    mappings.extend(from_biomappings(biomappings.load_mappings()))
    mappings.extend(from_gilda())
    mappings.extend(
        from_cache_df(
            "/Users/cthoyt/dev/biomappings/notebooks/cellosaurus_43_xrefs.tsv",
            "cellosaurus",
            prefixes=PREFIXES,
            version="43",
        )
    )

    mappings = filter_prefixes(mappings, PREFIXES)

    validate_mappings(mappings)

    click.echo(f"Loaded {len(mappings):,} positive mappings")
    click.echo(str_source_target_counts(mappings))

    mappings = process(mappings, upgrade_prefixes=PREFIXES)

    neo4j_path = MODULE.join("neo4j")
    click.echo(f"Output all mappings to {neo4j_path}")
    write_neo4j(mappings, neo4j_path)

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

    priority_mapping = prioritize(mappings, ["efo", "cellosaurus", "ccle", "depmap"])
    click.echo(f"Consolidated to a priority mapping of {len(priority_mapping):,} mappings")

    sssom_path = MODULE.join(name="reproduction_prioritized.tsv")
    click.echo(f"Output to {sssom_path}")
    write_sssom(priority_mapping, sssom_path)

    pickle_path = MODULE.join(name="reproduction_prioritized.pkl")
    click.echo(f"Output to {pickle_path}")
    write_pickle(priority_mapping, pickle_path)


if __name__ == "__main__":
    main()
