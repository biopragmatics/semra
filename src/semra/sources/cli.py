"""CLI for running all semra custom mapping getter functions."""

import click
from tqdm import tqdm


@click.command()
def main() -> None:
    """Run all custom SeMRA mapping getters."""
    from semra.sources import SOURCE_RESOLVER

    for func in tqdm(list(SOURCE_RESOLVER)):
        tqdm.write(f"Getting mappings with: `{func.__name__}`")
        m = func()
        click.echo(f"Got {len(m)} custom mappings")


if __name__ == "__main__":
    main()
