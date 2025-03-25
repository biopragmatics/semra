"""Generate a summary over the landscape analyses."""

import json
from pathlib import Path

import click
import pandas as pd

from semra import Configuration

HERE = Path(__file__).parent.resolve()


@click.command()
def main() -> None:
    """Generate a summary over the landscape analyses."""
    rows = []
    for directory in HERE.iterdir():
        if not directory.is_dir():
            continue

        row = {"name": directory.name}

        statistics_path = directory.joinpath("stats.json")
        if not statistics_path.is_file():
            continue
        row.update(json.loads(statistics_path.read_text()))

        configuration_path = directory.joinpath("configuration.json")
        configuration = Configuration.model_validate_json(configuration_path.read_text())
        row["zenodo"] = configuration.zenodo_url()
        rows.append(row)
    df = pd.DataFrame(rows).set_index("name")
    df = df[["raw_term_count", "unique_term_count", "reduction", "zenodo"]]
    df["reduction"] = df["reduction"].map(lambda r: f"{r:.1%}")
    df = df.astype(str)
    click.echo("\nTable as LaTeX for paper\n")
    click.echo(df.to_latex(label="landscape-summary-table", caption=""))
    click.echo("\nTable as markdown for repo\n")
    click.echo(df.to_markdown())


if __name__ == "__main__":
    main()
