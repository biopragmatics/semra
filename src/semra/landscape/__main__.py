"""Run all landscape builds."""

import click

import semra.landscape.anatomy
import semra.landscape.cells
import semra.landscape.complexes
import semra.landscape.diseases
import semra.landscape.genes


@click.command()
@click.pass_context
def main(ctx: click.Context):
    """Run all landscape builds."""
    ctx.invoke(semra.landscape.complexes.main)
    ctx.invoke(semra.landscape.anatomy.main)
    ctx.invoke(semra.landscape.cells.main)
    ctx.invoke(semra.landscape.diseases.main)
    ctx.invoke(semra.landscape.genes.main)


if __name__ == "__main__":
    main()
