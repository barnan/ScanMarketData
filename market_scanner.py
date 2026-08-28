import argparse
import os
import time
import warnings

import numpy as np
import pandas as pd
import yfinance as yf

from indicator_definition import *
from indicator_calculators import *
from scoring import *
from stock_universe import StockUniverse

warnings.filterwarnings("ignore")


# ============================================================
# CONFIGURATION
# ============================================================

DATA_PERIOD = "2y"
DATA_INTERVAL = "1d"

OUTPUT_DIR = "results"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "breakout_candidates.csv")

MIN_PRICE = 1.0                             # GPT -> 5.0
MIN_AVG_DOLLAR_VOLUME = 1_000_000           # GPT -> 1_000_000
TOP_N = 30

# Minimum number of historical rows required
MIN_HISTORY = 220


# ============================================================
# DOWNLOAD DATA
# ============================================================

def download_stock(ticker):
    """Download historical OHLCV data."""
    try:
        df = yf.download(
            ticker,
            period=DATA_PERIOD,
            interval=DATA_INTERVAL,
            auto_adjust=True,
            progress=False,
            threads=False,
        )

        if df.empty:
            print(f"Empty data for {ticker}")
            return None

        # yfinance may return MultiIndex columns.
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        required = ["Open", "High", "Low", "Close", "Volume"]

        if not all(column in df.columns for column in required):
            print(f"Missing columns: {ticker}")
            return None

        df = df[required].copy()
        df = df.dropna()

        if len(df) < MIN_HISTORY:
            print(f"Insufficient history for {ticker}")
            return None

        return df

    except Exception as e:
        print(f"ERROR downloading {ticker}: {e}")
        return None


# ============================================================
# SINGLE STOCK ANALYSIS
# ============================================================

def analyze_stock(
    ticker,
    indicators: Iterable[IndicatorDefinition] | None = None,
):
    if indicators is None:
        indicators = ACTIVE_INDICATORS

    indicators = list(indicators)

    df = download_stock(ticker)

    if df is None:
        return None

    # Basic liquidity/price filter. This is intentionally separate from the optional scoring indicators.
    latest_raw = df.iloc[-1]

    avg_dollar_volume = (
        df["Close"]
        .mul(df["Volume"])
        .rolling(20)
        .mean()
        .iloc[-1]
    )

    if latest_raw["Close"] < MIN_PRICE:
        return None

    if avg_dollar_volume < MIN_AVG_DOLLAR_VOLUME:
        return None

    # Only run calculators required by the selected scoring delegates.
    df = calculate_selected_indicators(df, indicators)

    score, reasons, warnings_list = calculate_breakout_score(
        df,
        indicators,
    )

    latest = df.iloc[-1]

    # --------------------------------------------------------
    # Output record
    #
    # Optional indicator values are only populated if their
    # corresponding calculation was selected.
    # --------------------------------------------------------

    def value(column, multiplier=1.0, decimals=2):
        """Safely retrieve an optional calculated value."""
        if column not in latest.index:
            return np.nan

        result = latest[column]

        if pd.isna(result):
            return np.nan

        return round(float(result) * multiplier, decimals)

    result = {
        "Ticker": ticker,
        "Date": df.index[-1].strftime("%Y-%m-%d"),
        "Score": score,
        "Close": round(float(latest["Close"]), 2),

        "SMA20": value("SMA20"),
        "SMA50": value("SMA50"),
        "SMA200": value("SMA200"),

        "RSI": value("RSI", decimals=1),
        "ADX": value("ADX", decimals=1),
        "ATR_Pct": value("ATR_PCT", multiplier=100),

        "RelVolume": value("REL_VOLUME"),
        "BBWidth": value("BB_WIDTH"),
        "VolatilityRatio": value("VOLATILITY_RATIO"),

        "Return5D": value("RETURN_5D", multiplier=100),
        "Return20D": value("RETURN_20D", multiplier=100),
        "Return60D": value("RETURN_60D", multiplier=100),

        "DistHigh20": value("DIST_HIGH20", multiplier=100),
        "DistHigh50": value("DIST_HIGH50", multiplier=100),

        "AvgDollarVolume": value(
            "AVG_DOLLAR_VOLUME_20",
            multiplier=1 / 1_000_000,
        ),

        "Reasons": " | ".join(reasons),
        "Warnings": " | ".join(warnings_list),
    }

    return result


# ============================================================
# MAIN SCANNER
# ============================================================

def scan_tickers(tickers, indicators=None):
    """Scan an already-created list of tickers.

    This function deliberately knows nothing about S&P 500, Nasdaq-100,
    Dow Jones, or any other stock universe.
    """
    if indicators is None:
        indicators = ACTIVE_INDICATORS

    indicators = list(indicators)
    results = []

    for i, ticker in enumerate(tickers, start=1):
        print(f"[{i:3d}/{len(tickers)}] {ticker:8s}", end=" ")

        result = analyze_stock(ticker, indicators)

        if result is None:
            print("SKIP")
        else:
            results.append(result)
            print(f"Score = {result['Score']:3d}")

        time.sleep(0.1)

    return results


def save_and_display_results(results):
    """Save scan results and display the top candidates."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    results_df = pd.DataFrame(results)

    if results_df.empty:
        print("\nNo stocks passed the filters.")
        return

    results_df = (
        results_df
        .sort_values("Score", ascending=False)
        .reset_index(drop=True)
    )

    results_df.to_csv(OUTPUT_FILE, index=False)

    display_columns = [
        "Ticker", "Score", "Close", "RSI", "ADX", "RelVolume",
        "DistHigh20", "DistHigh50", "VolatilityRatio", "Return20D",
    ]
    display_columns = [
        column for column in display_columns
        if column in results_df.columns
    ]

    print()
    print("=" * 70)
    print("TOP PRE-BREAKOUT CANDIDATES")
    print("=" * 70)
    print()
    print(results_df[display_columns].head(TOP_N).to_string(index=False))

    print()
    print(f"Full results saved to: {OUTPUT_FILE}")

    top_file = os.path.join(OUTPUT_DIR, "top_candidates.csv")
    results_df.head(TOP_N).to_csv(top_file, index=False)
    print(f"Top {TOP_N} saved to: {top_file}")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Scan a configurable stock universe for pre-breakout candidates."
    )
    parser.add_argument(
        "--universe",
        default=None,
        help="Name of a universe from the universe JSON configuration.",
    )
    parser.add_argument(
        "--universes-file",
        default="market_universes.json",
        help="JSON file containing stock universe definitions.",
    )
    parser.add_argument(
        "--tickers",
        nargs="+",
        help="Explicit ticker symbols. Overrides --universe.",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    print()
    print("=" * 70)
    print("PRE-BREAKOUT STOCK SCANNER")
    print("=" * 70)
    print()

    print("List of the active indicators:")
    for indicator in ACTIVE_INDICATORS:
        print(f"  - {indicator.name} ({indicator.max_points} pts)")
    print()

    if args.tickers:
        tickers = StockUniverse.normalize_tickers(args.tickers)
        universe_name = "explicit tickers"
    else:
        universe = StockUniverse.from_json(args.universes_file)
        universe_name = args.universe or "sp500"
        tickers = universe.get_tickers(universe_name)

    print(f"Universe: {universe_name}")
    print(f"Found {len(tickers)} stocks.")
    print()

    results = scan_tickers(tickers, ACTIVE_INDICATORS)
    save_and_display_results(results)

# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()
