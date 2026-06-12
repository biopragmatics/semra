"""CLI for running all semra custom mapping getter functions."""

import click


@click.command()
def main() -> None:
    """Run all custom SeMRA mapping getters."""
    import time

    from humanize import naturaldelta
    from tqdm import tqdm

    from semra.io import from_sssom_pydantic
    from semra.sources import SOURCE_RESOLVER, normalize_custom_func_name

    for func in tqdm(list(SOURCE_RESOLVER), desc="Getting SeMRA sources", unit="source"):
        name = normalize_custom_func_name(func)
        tqdm.write(f"[{name}] getting mappings")
        start = time.time()
        try:
            mappings = from_sssom_pydantic(func())
        except Exception as e:
            tqdm.write(click.style(f"[{name}] failed:\n{e}", fg="red"))
        else:
            tqdm.write(
                f"[{name}] got {len(mappings):,} mappings in {naturaldelta(time.time() - start)}"
            )


if __name__ == "__main__":
    main()
