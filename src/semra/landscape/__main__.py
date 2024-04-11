"""Run all landscape builds."""

import click

import semra.landscape.anatomy
import semra.landscape.cells
import semra.landscape.complexes
import semra.landscape.diseases
import semra.landscape.genes


FUNCTIONS = [
    ("Complexes", semra.landscape.complexes.main),
    ("Anatomy", semra.landscape.anatomy.main),
    ("Cells and Cell Lines", semra.landscape.cells.main),
    ("Diseases", semra.landscape.diseases.main),
    ("Genes", semra.landscape.genes.main),
]


@click.command()
@click.pass_context
def main(ctx: click.Context):
    """Run all landscape builds."""
    for label, func in FUNCTIONS:
        click.secho(label, bold=True, fg="green")
        ctx.invoke(func)


if __name__ == "__main__":
    main()
