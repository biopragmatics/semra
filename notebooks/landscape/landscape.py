"""Generate a summary over the landscape analyses."""

import click

from semra.landscape.cli import compile_landscape_metaanalysis


@click.command()
def main() -> None:
    """Generate a summary over the landscape analyses."""
    click.echo("Note that this script is now part of the main `semra landscape` workflow")
    compile_landscape_metaanalysis()


if __name__ == "__main__":
    main()
