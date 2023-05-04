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
from tabulate import tabulate

from semra.api import (
    count_source_target,
    filter_prefixes,
    prioritize,
    process,
    project,
    validate_mappings,
    write_sssom,
)
from semra.sources import from_biomappings, from_cache_df, from_gilda, from_pyobo

PREFIXES = {
    "efo",
    "cellosaurus",
    "depmap",
    "ccle",
    # "clo", "cl", "bto",
}


@click.command()
def main():
    # 1. load mappings
    mappings = []
    mappings.extend(from_pyobo("efo"))
    mappings.extend(from_pyobo("depmap", version="22Q4"))
    mappings.extend(from_pyobo("ccle"))
    mappings.extend(from_biomappings(biomappings.load_mappings()))
    mappings.extend(from_gilda())
    mappings.extend(
        from_cache_df(
            "/Users/cthoyt/dev/biomappings/notebooks/cellosaurus_43_xrefs.tsv",
            "cellosaurus",
            prefixes=PREFIXES,
        )
    )

    mappings = filter_prefixes(mappings, PREFIXES)

    validate_mappings(mappings)

    click.echo(f"Loaded {len(mappings):,} positive mappings")
    so_prefix_counter = count_source_target(mappings)
    click.echo(
        tabulate(
            [(s, o, c) for (s, o), c in so_prefix_counter.most_common()],
            headers=["source prefix", "target prefix", "count"],
            tablefmt="github",
        )
    )

    mappings = process(mappings, upgrade_prefixes=PREFIXES)

    # Produce a consolidation mapping
    for s_prefix, t_prefix in [
        ("ccle", "efo"),
        ("ccle", "depmap"),
    ]:
        consolidation_mappings = project(mappings, s_prefix, t_prefix)
        click.echo(f"Consolidated to {len(consolidation_mappings):,} mappings between {s_prefix} and {t_prefix}")

        path = pystow.join("semra", name=f"reproduction_{s_prefix}_{t_prefix}.tsv")
        click.echo(f"Output to {path}")
        write_sssom(consolidation_mappings, path)

    priority_mapping = prioritize(mappings, ["efo", "cellosaurus", "ccle", "depmap"])
    click.echo(f"Consolidated to a priority mapping of {len(priority_mapping):,} mappings")
    path = pystow.join("semra", name="reproduction_prioritized.tsv")
    click.echo(f"Output to {path}")
    write_sssom(priority_mapping, path)

    import pickle

    pystow.join("semra", name="reproduction_prioritized.pkl").write_bytes(pickle.dumps(priority_mapping))


if __name__ == "__main__":
    main()
