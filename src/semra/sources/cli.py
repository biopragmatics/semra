"""CLI for running all semra custom mapping getter functions."""

import click
from tqdm import tqdm


@click.command()
def main() -> None:
    """Run all custom SeMRA mapping getters."""
    from semra.sources import SOURCE_RESOLVER, _normalize_name

    for func in tqdm(list(SOURCE_RESOLVER), desc="Getting SeMRA sources", unit="source"):
        name = _normalize_name(func)
        tqdm.write(f"[{name}] getting mappings")
        try:
            mappings = func()
        except Exception as e:
            tqdm.write(f"[{name}] failed:\n{e}")
        else:
            tqdm.write(f"[{name}] got {len(mappings):,} mappings")


if __name__ == "__main__":
    main()
