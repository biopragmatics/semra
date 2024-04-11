"""Generate a summary over the landscape analyses."""

import json
from pathlib import Path

import pandas as pd

HERE = Path(__file__).parent.resolve()


def main() -> None:
    """Generate a summary over the landscape analyses."""
    rows = []
    for directory in HERE.iterdir():
        if not directory.is_dir():
            continue
        path = directory.joinpath("stats.json")
        if not path.is_file():
            continue
        row = json.loads(path.read_text())
        row["name"] = directory.name
        rows.append(row)
    df = pd.DataFrame(rows).set_index("name")
    df = df[["raw_term_count", "unique_term_count", "reduction"]]
    print(df.to_markdown(tablefmt="github"))


if __name__ == "__main__":
    main()
