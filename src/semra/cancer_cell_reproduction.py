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
import bioregistry
import click
import pystow
from tabulate import tabulate
from tqdm.auto import tqdm

from semra.api import (
    assemble_evidences,
    count_source_target,
    filter_negatives,
    filter_prefixes,
    filter_self_matches,
    infer_chains,
    infer_reversible,
    project,
    upgrade_mutual_dbxrefs,
    prioritize,
    write_sssom,
)
from semra.rules import DB_XREF
from semra.sources import from_biomappings, from_cache_df, from_pyobo
from semra.struct import Mapping

PREFIXES = {
    "efo",
    "cellosaurus",
    "depmap",
    "ccle",
    # "clo", "cl", "bto",
}


def echo_diff(before: int, mappings: list[Mapping], *, verb: str) -> None:
    click.echo(f"{verb} from {before:,} to {len(mappings):,} mappings (Δ={len(mappings) - before:,})")


@click.command()
def main():
    # 1. load mappings
    mappings = []
    mappings.extend(from_pyobo("efo"))
    mappings.extend(from_pyobo("depmap", version="22Q4"))
    mappings.extend(from_pyobo("ccle"))
    mappings.extend(from_biomappings(biomappings.load_mappings()))
    mappings.extend(
        from_cache_df(
            "/Users/cthoyt/dev/biomappings/notebooks/cellosaurus_43_xrefs.tsv",
            "cellosaurus",
            prefixes=PREFIXES,
        )
    )

    mappings = filter_prefixes(mappings, PREFIXES)

    for mapping in tqdm(mappings, desc="validating", unit_scale=True, unit="mapping"):
        if bioregistry.normalize_prefix(mapping.s.prefix) != mapping.s.prefix:
            raise ValueError(f"invalid subject prefix: {mapping}.")
        if bioregistry.normalize_prefix(mapping.o.prefix) != mapping.o.prefix:
            raise ValueError(f"invalid object prefix: {mapping}.")
        if not bioregistry.is_valid_identifier(mapping.s.prefix, mapping.s.identifier):
            raise ValueError(
                f"invalid mapping subject: {mapping}. Use regex {bioregistry.get_pattern(mapping.o.prefix)}"
            )
        if not bioregistry.is_valid_identifier(mapping.o.prefix, mapping.o.identifier):
            raise ValueError(
                f"invalid mapping object: {mapping}. Use regex {bioregistry.get_pattern(mapping.o.prefix)}"
            )

    click.echo(f"Loaded {len(mappings):,} positive mappings")
    so_prefix_counter = count_source_target(mappings)
    click.echo(
        tabulate(
            [(s, o, c) for (s, o), c in so_prefix_counter.most_common()],
            headers=["source prefix", "target prefix", "count"],
            tablefmt="github",
        )
    )

    negatives = from_biomappings(biomappings.load_false_mappings())
    click.echo(f"Loaded {len(negatives):,} negative mappings")

    before = len(mappings)
    mappings = filter_negatives(mappings, negatives)
    echo_diff(before, mappings, verb="Filtered negative mappings")

    # deduplicate
    before = len(mappings)
    mappings = assemble_evidences(mappings)
    echo_diff(before, mappings, verb="Assembled")

    # only keep relevant prefixes
    # mappings = filter_prefixes(mappings, PREFIXES)
    # click.echo(f"Filtered to {len(mappings):,} mappings")

    # 2. using the assumption that primary mappings from each of these
    # resources to each other are exact matches, rewrite the prefixes
    mappings = upgrade_mutual_dbxrefs(mappings, PREFIXES)

    # remove mapping between self, such as EFO-EFO
    click.echo("Removing self mappings (i.e., within a given semantic space)")
    before = len(mappings)
    mappings = filter_self_matches(mappings)
    echo_diff(before, mappings, verb="Filtered")

    # remove dbxrefs
    click.echo("Removing unqualified database xrefs")
    before = len(mappings)
    mappings = [m for m in mappings if m.p != DB_XREF]
    echo_diff(before, mappings, verb="Filtered")

    # 3. Inference based on adding reverse relations then doing multi-chain hopping
    click.echo("Inferring reverse mappings")
    before = len(mappings)
    mappings = infer_reversible(mappings)
    echo_diff(before, mappings, verb="Inferred")

    click.echo("Inferring based on chains")
    before = len(mappings)
    mappings = infer_chains(mappings)
    echo_diff(before, mappings, verb="Inferred")

    # 4/5. Filtering negative
    click.echo("Filtering out negative mappings")
    before = len(mappings)
    mappings = filter_negatives(mappings, negatives)
    echo_diff(before, mappings, verb="Filtered negative mappings")

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


if __name__ == "__main__":
    main()
