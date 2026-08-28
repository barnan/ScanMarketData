import os
import time
import warnings

import requests
from io import StringIO

import numpy as np
import pandas as pd
import yfinance as yf

from indicator_definition import *
from indicator_calculators import *
from scoring import *

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
# UNIVERSE
# ============================================================

def get_sp500_tickers():
    """Get current S&P 500 constituents from Wikipedia."""
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    headers = {"User-Agent": "Mozilla/5.0"}

    response = requests.get(url, headers=headers)
    response.raise_for_status()

    tables = pd.read_html(StringIO(response.text))
    sp500 = tables[0]

    tickers = sp500["Symbol"].tolist()

    # Yahoo Finance uses '-' instead of '.' for some tickers.
    tickers = [ticker.replace(".", "-") for ticker in tickers]

    return tickers


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
            return None

        # yfinance may return MultiIndex columns.
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        required = ["Open", "High", "Low", "Close", "Volume"]

        if not all(column in df.columns for column in required):
            return None

        df = df[required].copy()
        df = df.dropna()

        if len(df) < MIN_HISTORY:
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

    # Basic liquidity/price filter. This is intentionally separate
    # from the optional scoring indicators.
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

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print()
    print("=" * 70)
    print("PRE-BREAKOUT STOCK SCANNER")
    print("=" * 70)
    print()

    print("Active indicators:")
    for indicator in ACTIVE_INDICATORS:
        print(f"  - {indicator.name} ({indicator.max_points} pts)")
    print()

    print("Downloading S&P 500 universe...")
    tickers = get_sp500_tickers()

    print(f"Found {len(tickers)} stocks.")
    print()

    results = []

    for i, ticker in enumerate(tickers, start=1):
        print(
            f"[{i:3d}/{len(tickers)}] "
            f"{ticker:8s}",
            end=" ",
        )

        result = analyze_stock(
            ticker,
            ACTIVE_INDICATORS,
        )

        if result is None:
            print("SKIP")
        else:
            results.append(result)
            print(f"Score = {result['Score']:3d}")

        # Small delay to be polite to the data provider.
        time.sleep(0.1)

    # --------------------------------------------------------
    # Create dataframe
    # --------------------------------------------------------

    results_df = pd.DataFrame(results)

    if results_df.empty:
        print("\nNo stocks passed the filters.")
        return

    # Sort by score
    results_df = (
        results_df
        .sort_values("Score", ascending=False)
        .reset_index(drop=True)
    )

    # --------------------------------------------------------
    # Save all results
    # --------------------------------------------------------

    results_df.to_csv(OUTPUT_FILE, index=False)

    # --------------------------------------------------------
    # Display top candidates
    # --------------------------------------------------------

    display_columns = [
        "Ticker",
        "Score",
        "Close",
        "RSI",
        "ADX",
        "RelVolume",
        "DistHigh20",
        "DistHigh50",
        "VolatilityRatio",
        "Return20D",
    ]

    # Only display columns that exist. This makes the output robust
    # if you later remove optional calculations/output fields.
    display_columns = [
        column
        for column in display_columns
        if column in results_df.columns
    ]

    print()
    print("=" * 70)
    print("TOP PRE-BREAKOUT CANDIDATES")
    print("=" * 70)
    print()

    print(
        results_df[display_columns]
        .head(TOP_N)
        .to_string(index=False)
    )

    print()
    print(f"Full results saved to: {OUTPUT_FILE}")

    # --------------------------------------------------------
    # Save top candidates separately
    # --------------------------------------------------------

    top_file = os.path.join(OUTPUT_DIR, "top_candidates.csv")

    results_df.head(TOP_N).to_csv(
        top_file,
        index=False,
    )

    print(f"Top {TOP_N} saved to: {top_file}")


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()
