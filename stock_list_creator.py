import argparse
from io import StringIO
from pathlib import Path

import pandas as pd
import requests


def normalize_ticker(ticker: str) -> str:
    return ticker.strip().replace(".", "-")


def get_sp500_tickers() -> list[str]:
    """Create an S&P 500 ticker list from Wikipedia."""
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    response.raise_for_status()

    tables = pd.read_html(StringIO(response.text))
    tickers = tables[0]["Symbol"].dropna().astype(str)
    return list(dict.fromkeys(normalize_ticker(t) for t in tickers))


def get_tickers_from_csv(input_file: str, column: str) -> list[str]:
    """Create a ticker list from any CSV containing a ticker column."""
    df = pd.read_csv(input_file)
    if column not in df.columns:
        raise ValueError(
            f"Ticker column '{column}' not found. Available columns: {list(df.columns)}"
        )

    tickers = df[column].dropna().astype(str)
    return list(dict.fromkeys(normalize_ticker(t) for t in tickers))


def save_tickers(tickers: list[str], output_file: str) -> None:
    path = Path(output_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "# One Yahoo Finance ticker per line\n" + "\n".join(tickers) + "\n",
        encoding="utf-8",
    )
    print(f"Saved {len(tickers)} tickers to {path}")


def main():
    parser = argparse.ArgumentParser(
        description="Create a stock list for the market scanner."
    )
    parser.add_argument(
        "--source",
        choices=["sp500", "csv"],
        required=True,
        help="Where to obtain the stock universe.",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Output ticker-list file (one ticker per line).",
    )
    parser.add_argument(
        "--input",
        help="Input CSV when --source=csv.",
    )
    parser.add_argument(
        "--column",
        default="Symbol",
        help="Ticker column when --source=csv (default: Symbol).",
    )
    args = parser.parse_args()

    if args.source == "sp500":
        tickers = get_sp500_tickers()
    else:
        if not args.input:
            parser.error("--input is required when --source=csv")
        tickers = get_tickers_from_csv(args.input, args.column)

    save_tickers(tickers, args.output)


if __name__ == "__main__":
    main()
