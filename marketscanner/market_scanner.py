import argparse
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

from .indicator_definition import *
from .indicator_calculators import *
from .market_context import calculate_market_context, calculate_sector_context
from .scoring import *
from .stock_universe import StockUniverse
from .strategy_loader import (
    load_strategy,
    resolve_indicators_for_strategy,
)

warnings.filterwarnings("ignore")


# ============================================================
# CONFIGURATION
# ============================================================

DATA_PERIOD = "2y"
DATA_INTERVAL = "1d"

PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = PACKAGE_DIR.parent

OUTPUT_DIR = PROJECT_DIR / "results"
OUTPUT_FILE = OUTPUT_DIR / "bullish_setup.csv"

TOP_N = 30

# Minimum number of historical rows required
MIN_HISTORY = 220


# ============================================================
# INPUT FOLDER DEFINITIONS
# ============================================================

UNIVERSES_DIR = PACKAGE_DIR / "universes"
STRATEGIES_DIR = PACKAGE_DIR / "strategies"

DEFAULT_UNIVERSES_FILE = UNIVERSES_DIR / "market_universes.json"
DEFAULT_STRATEGY_FILE = STRATEGIES_DIR / "default.json"

# ============================================================
# DOWNLOAD DATA
# ============================================================

def download_stock(ticker, as_of=None):
    """Download historical OHLCV data."""
    try:
        download_kwargs = {
            "period": DATA_PERIOD,
            "interval": DATA_INTERVAL,
            "auto_adjust": True,
            "progress": False,
            "threads": False,
        }
        if as_of is not None:
            as_of_date = pd.Timestamp(as_of).normalize()
            download_kwargs.pop("period")
            download_kwargs["start"] = as_of_date - pd.DateOffset(years=2)
            download_kwargs["end"] = as_of_date + pd.Timedelta(days=1)

        df = yf.download(
            ticker,
            **download_kwargs,
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


def download_context_series(symbol, as_of=None):
    """Download one benchmark close series for optional context scoring."""
    try:
        download_kwargs = {
            "period": DATA_PERIOD,
            "interval": DATA_INTERVAL,
            "auto_adjust": True,
            "progress": False,
            "threads": False,
        }
        if as_of is not None:
            as_of_date = pd.Timestamp(as_of).normalize()
            download_kwargs.pop("period")
            download_kwargs["start"] = as_of_date - pd.DateOffset(years=2)
            download_kwargs["end"] = as_of_date + pd.Timedelta(days=1)

        frame = yf.download(symbol, **download_kwargs)
        if isinstance(frame.columns, pd.MultiIndex):
            frame.columns = frame.columns.get_level_values(0)
        if frame.empty or "Close" not in frame.columns:
            return None
        return frame[["Close"]].dropna()
    except Exception as error:
        print(f"ERROR downloading context {symbol}: {error}")
        return None


# ============================================================
# SINGLE STOCK ANALYSIS
# ============================================================

def analyze_stock(
    ticker,
    indicators: Iterable[IndicatorDefinition] | None = None,
    as_of=None,
    context_score: float | None = None,
    context_weight: float = 0.0,
    filters: dict | None = None,
):
    if indicators is None:
        indicators = DEFAULT_INDICATORS

    indicators = list(indicators)

    df = download_stock(ticker, as_of=as_of)

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

    filters = filters or {}
    minimum_price = float(filters.get("min_price", MIN_PRICE))
    minimum_dollar_volume = float(
        filters.get("min_avg_dollar_volume", MIN_AVG_DOLLAR_VOLUME)
    )

    if latest_raw["Close"] < minimum_price:
        return None

    if avg_dollar_volume < minimum_dollar_volume:
        return None

    # Only run calculators required by the selected scoring delegates.
    df = calculate_selected_indicators(df, indicators, as_of=as_of)

    maximum_resistance_extension = filters.get("max_distance_above_resistance")
    if (
        maximum_resistance_extension is not None
        and "HIGH20_PREVIOUS" in df.columns
        and pd.notna(df["HIGH20_PREVIOUS"].iloc[-1])
        and latest_raw["Close"]
        > df["HIGH20_PREVIOUS"].iloc[-1] * (1 + float(maximum_resistance_extension))
    ):
        return None

    score, reasons, warnings_list = calculate_breakout_score(
        df,
        indicators,
    )

    if context_score is not None and context_weight > 0:
        score = round(
            score * (1 - context_weight / 100)
            + context_score * (context_weight / 100)
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
        "AsOf": pd.Timestamp(as_of).normalize().strftime("%Y-%m-%d")
        if as_of is not None
        else df.index[-1].strftime("%Y-%m-%d"),
        "Date": df.index[-1].strftime("%Y-%m-%d"),
        "Score": score,
        "ContextScore": round(context_score, 2) if context_score is not None else np.nan,
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

def scan_tickers(
    tickers,
    indicators=None,
    as_of=None,
    context_score: float | None = None,
    context_weight: float = 0.0,
    filters: dict | None = None,
):
    """Scan an already-created list of tickers.

    This function deliberately knows nothing about S&P 500, Nasdaq-100,
    Dow Jones, or any other stock universe.
    """
    if indicators is None:
        indicators = DEFAULT_INDICATORS

    indicators = list(indicators)
    results = []

    for i, ticker in enumerate(tickers, start=1):
        print(f"[{i:3d}/{len(tickers)}] {ticker:8s}", end=" ")

        result = analyze_stock(
            ticker,
            indicators,
            as_of=as_of,
            context_score=context_score,
            context_weight=context_weight,
            filters=filters,
        )

        if result is None:
            print("SKIP")
        else:
            results.append(result)
            print(f"Score = {result['Score']:3d}")

        time.sleep(0.1)

    return results


def save_and_display_results(results):
    """Save scan results and display the top candidates."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    results_df = pd.DataFrame(results)

    if results_df.empty:
        print("\nNo stocks passed the filters.")
        return

    results_df = (
        results_df
        .sort_values("Score", ascending=False)
        .reset_index(drop=True)
    )

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

    top_file = OUTPUT_DIR / "top_candidates.csv"
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
        default=DEFAULT_UNIVERSES_FILE,
        help="JSON file containing stock universe definitions.",
    )
    parser.add_argument(
        "--strategy",
        "--strategy-file",
        dest="strategy_file",
        default=DEFAULT_STRATEGY_FILE,
        help="JSON file containing strategy definition.",
    )
    parser.add_argument(
        "--tickers",
        nargs="+",
        help="Explicit ticker symbols. Overrides --universe.",
    )
    parser.add_argument(
        "--as-of",
        type= str,
        default=None,
        help="Analyze only data available on or before this date (YYYY-MM-DD).",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    print()
    print("=" * 70)
    print("PRE-BREAKOUT STOCK SCANNER")
    print("=" * 70)
    print()

    strategy = load_strategy(args.strategy_file)
    selected_indicators = resolve_indicators_for_strategy(strategy)

    print("List of the active indicators:")
    for indicator in selected_indicators:
        print(f"  - {indicator.name} ({indicator.max_points} pts)")
    print()

    strategy_name = strategy.name
    if args.tickers:
        tickers = StockUniverse.normalize_tickers(args.tickers)
        universe_name = "explicit tickers"
    else:
        universe = StockUniverse.from_json(args.universes_file)
        universe_name = args.universe or "sp500"
        tickers = universe.get_tickers(universe_name)

    print(f"Strategy: {strategy_name}")
    print(f"Universe: {universe_name}")
    print(f"Found {len(tickers)} stocks.")
    print()

    context_score = None
    context_weight = 0.0
    if strategy.context:
        symbols = {
            "sp500": "^GSPC",
            "vix": "^VIX",
            "dxy": "DX-Y.NYB",
            "gold": "GC=F",
            "silver": "SI=F",
            "gdx": "GDX",
            "gdxj": "GDXJ",
            "slv": "SLV",
        }
        context_frames = {
            name: frame
            for name, symbol in symbols.items()
            if (frame := download_context_series(symbol, as_of=args.as_of)) is not None
        }
        if "sp500" in context_frames:
            market_context = calculate_market_context(context_frames, args.as_of or pd.Timestamp.today())
            sector_context = calculate_sector_context(context_frames, args.as_of or pd.Timestamp.today())
            context_score = 100 * (market_context.score + sector_context.score) / 24
            context_config = strategy.context or {}
            context_weight = float(
                context_config.get("general_market", {}).get("weight", 15)
                + context_config.get("sector", {}).get("weight", 25)
            )
            print(f"Market context score: {market_context.score:.1f}/9")
            print(f"Sector context score: {sector_context.score:.1f}/15")
            for warning in market_context.warnings + sector_context.warnings:
                print(f"Context warning: {warning}")

    results = scan_tickers(
        tickers,
        selected_indicators,
        as_of=args.as_of,
        context_score=context_score,
        context_weight=context_weight,
        filters=strategy.filters,
    )
    save_and_display_results(results)

# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()
