"""Update the module level docstrings for landscape configurations."""

from pathlib import Path

import click

from semra.landscape import CONFIGURATIONS

__all__ = [
    "update_landscape_module_docstrings",
]

HERE = Path(__file__).parent.resolve()


@click.command()
def update_landscape_module_docstrings() -> None:
    """Update the module level docstrings for landscape configurations."""
    for conf in CONFIGURATIONS:
        path = HERE.joinpath(conf.key).with_suffix(".py")
        text = path.read_text()
        lines = text.splitlines()
        idx = min(i for i, line in enumerate(lines[1:], start=1) if line.startswith('"""'))
        new = conf._get_header_text()
        path.write_text(new + "\n".join(lines[idx + 1 :]) + "\n")


if __name__ == "__main__":
    update_landscape_module_docstrings()
