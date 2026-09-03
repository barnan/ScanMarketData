"""Evaluate scanner picks at a later trading-day interval."""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import yfinance as yf


PROJECT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_RESULTS_DIR = PROJECT_DIR / "results"
DEFAULT_OUTPUT_FILE = Path(__file__).resolve().parent / "performance_results.csv"


def _default_results_file(results_dir: Path) -> Path:
    preferred = results_dir / "top_candidates.csv"
    if preferred.exists():
        return preferred

    fallback = results_dir / "bullish_setup.csv"
    if fallback.exists():
        return fallback

    raise FileNotFoundError(
        f"No scanner result CSV found in {results_dir}."
    )


def _download_forward_prices(
    ticker: str,
    as_of: pd.Timestamp,
    forward_days: int,
) -> pd.Series:
    end = as_of + pd.Timedelta(days=max(forward_days * 3, 30))
    prices = yf.download(
        ticker,
        start=as_of - pd.Timedelta(days=7),
        end=end + pd.Timedelta(days=1),
        interval="1d",
        auto_adjust=True,
        progress=False,
        threads=False,
    )

    if isinstance(prices.columns, pd.MultiIndex):
        prices.columns = prices.columns.get_level_values(0)

    if prices.empty or "Close" not in prices.columns:
        return pd.Series(dtype=float)

    close = prices["Close"].dropna()
    close.index = pd.to_datetime(close.index).tz_localize(None).normalize()
    return close


def evaluate_results(
    results_file: str | Path,
    as_of: str | pd.Timestamp,
    forward_days: int,
) -> pd.DataFrame:
    """Evaluate each scanner ticker after a number of trading days."""
    if forward_days < 1:
        raise ValueError("forward_days must be at least 1")

    evaluation_date = pd.Timestamp(as_of).normalize()
    scanner_results = pd.read_csv(results_file)
    if "Ticker" not in scanner_results.columns:
        raise ValueError("Scanner results must contain a 'Ticker' column")

    records = []
    for ticker in scanner_results["Ticker"].dropna().astype(str).unique():
        close = _download_forward_prices(ticker, evaluation_date, forward_days)
        baseline_dates = close.index[close.index <= evaluation_date]

        if baseline_dates.empty:
            records.append({
                "Ticker": ticker,
                "EvaluationDate": evaluation_date.date().isoformat(),
                "Status": "No price on or before evaluation date",
            })
            continue

        baseline_date = baseline_dates[-1]
        baseline_position = close.index.get_loc(baseline_date)
        target_position = baseline_position + forward_days

        if target_position >= len(close):
            records.append({
                "Ticker": ticker,
                "EvaluationDate": evaluation_date.date().isoformat(),
                "BaselineDate": baseline_date.date().isoformat(),
                "Status": "Insufficient forward data",
            })
            continue

        target_date = close.index[target_position]
        baseline_close = float(close.iloc[baseline_position])
        target_close = float(close.iloc[target_position])
        return_pct = (target_close / baseline_close - 1) * 100

        records.append({
            "Ticker": ticker,
            "EvaluationDate": evaluation_date.date().isoformat(),
            "BaselineDate": baseline_date.date().isoformat(),
            "TargetDate": target_date.date().isoformat(),
            "BaselineClose": round(baseline_close, 4),
            "TargetClose": round(target_close, 4),
            "ReturnPct": round(return_pct, 2),
            "HigherPrice": target_close > baseline_close,
            "Status": "Evaluated",
        })

    return pd.DataFrame(records)


def summarize_performance(evaluations: pd.DataFrame) -> dict[str, float | int]:
    """Return the aggregate higher-price percentage for evaluated picks."""
    evaluated = evaluations[evaluations["Status"] == "Evaluated"]
    total = len(evaluated)
    higher = int(evaluated["HigherPrice"].sum()) if total else 0

    return {
        "total_picks": len(evaluations),
        "evaluated_picks": total,
        "higher_price_picks": higher,
        "higher_price_percentage": round(100 * higher / total, 2) if total else 0.0,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate market-scanner CSV picks after a forward interval."
    )
    parser.add_argument("--as-of", required=True, help="Scanner evaluation date (YYYY-MM-DD).")
    parser.add_argument(
        "--forward-days",
        type=int,
        default=20,
        help="Number of forward trading days to evaluate (default: 20).",
    )
    parser.add_argument("--results-dir", type=Path, default=DEFAULT_RESULTS_DIR)
    parser.add_argument("--results-file", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_FILE)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    results_file = args.results_file or _default_results_file(args.results_dir)
    evaluations = evaluate_results(results_file, args.as_of, args.forward_days)
    summary = summarize_performance(evaluations)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    evaluations.to_csv(args.output, index=False)

    print(f"Results input: {results_file}")
    print(f"Evaluation date: {args.as_of}")
    print(f"Forward trading days: {args.forward_days}")
    print(f"Evaluated picks: {summary['evaluated_picks']}/{summary['total_picks']}")
    print(f"Higher-price picks: {summary['higher_price_picks']}")
    print(f"Higher-price percentage: {summary['higher_price_percentage']:.2f}%")
    print(f"Detailed results saved to: {args.output}")


if __name__ == "__main__":
    main()
