import os
import time
import warnings
from dataclasses import dataclass
from typing import Callable, Iterable

import requests
from io import StringIO

import numpy as np
import pandas as pd
import yfinance as yf

from ta.trend import SMAIndicator, EMAIndicator, MACD, ADXIndicator
from ta.momentum import RSIIndicator
from ta.volatility import AverageTrueRange, BollingerBands

warnings.filterwarnings("ignore")


# ============================================================
# CONFIGURATION
# ============================================================

DATA_PERIOD = "2y"
DATA_INTERVAL = "1d"

OUTPUT_DIR = "results"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "breakout_candidates.csv")

MIN_PRICE = 5.0
MIN_AVG_DOLLAR_VOLUME = 10_000_000
TOP_N = 30

# How close should price be to resistance?
RESISTANCE_DISTANCE = 0.05  # 5%

# Minimum number of historical rows required
MIN_HISTORY = 220


# ============================================================
# INDICATOR FRAMEWORK
# ============================================================

@dataclass(frozen=True)
class IndicatorDefinition:
    """
    A scoring indicator.

    calculator_names:
        Names of calculation delegates required by this indicator.
    scorer:
        Function that evaluates the latest row and returns:
        (points, reasons, warnings).
    max_points:
        Maximum points this indicator can contribute.
    """

    name: str
    calculator_names: tuple[str, ...]
    scorer: Callable[[pd.DataFrame], tuple[float, list[str], list[str]]]
    max_points: float


# ============================================================
# INDICATOR CALCULATORS
#
# Each method calculates one logical group of technical data.
# They are deliberately independent so the scanner can execute
# only the calculations needed by the selected indicators.
# ============================================================

def calculate_moving_averages(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate SMA20, SMA50, SMA200 and EMA20."""
    df = df.copy()
    close = df["Close"]

    df["SMA20"] = SMAIndicator(close=close, window=20).sma_indicator()
    df["SMA50"] = SMAIndicator(close=close, window=50).sma_indicator()
    df["SMA200"] = SMAIndicator(close=close, window=200).sma_indicator()
    df["EMA20"] = EMAIndicator(close=close, window=20).ema_indicator()

    return df


def calculate_rsi(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate RSI."""
    df = df.copy()
    df["RSI"] = RSIIndicator(close=df["Close"], window=14).rsi()
    return df


def calculate_macd(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate MACD, signal and histogram."""
    df = df.copy()

    macd = MACD(
        close=df["Close"],
        window_slow=26,
        window_fast=12,
        window_sign=9,
    )

    df["MACD"] = macd.macd()
    df["MACD_SIGNAL"] = macd.macd_signal()
    df["MACD_HIST"] = macd.macd_diff()

    return df


def calculate_atr(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate ATR and ATR as a percentage of price."""
    df = df.copy()

    atr = AverageTrueRange(
        high=df["High"],
        low=df["Low"],
        close=df["Close"],
        window=14,
    )

    df["ATR"] = atr.average_true_range()
    df["ATR_PCT"] = df["ATR"] / df["Close"]

    return df


def calculate_adx(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate ADX and directional indicators."""
    df = df.copy()

    adx = ADXIndicator(
        high=df["High"],
        low=df["Low"],
        close=df["Close"],
        window=14,
    )

    df["ADX"] = adx.adx()
    df["DI_PLUS"] = adx.adx_pos()
    df["DI_MINUS"] = adx.adx_neg()

    return df


def calculate_bollinger_bands(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate Bollinger Band high, low and width."""
    df = df.copy()

    bb = BollingerBands(
        close=df["Close"],
        window=20,
        window_dev=2,
    )

    df["BB_HIGH"] = bb.bollinger_hband()
    df["BB_LOW"] = bb.bollinger_lband()
    df["BB_WIDTH"] = bb.bollinger_wband()

    return df


def calculate_volume(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate volume averages, relative volume and dollar volume."""
    df = df.copy()
    volume = df["Volume"]
    close = df["Close"]

    df["VOL5"] = volume.rolling(5).mean()
    df["VOL20"] = volume.rolling(20).mean()
    df["VOL50"] = volume.rolling(50).mean()
    df["REL_VOLUME"] = volume / df["VOL20"]

    df["DOLLAR_VOLUME"] = close * volume
    df["AVG_DOLLAR_VOLUME_20"] = df["DOLLAR_VOLUME"].rolling(20).mean()

    return df


def calculate_resistance(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate previous resistance levels.

    The shift(1) is important: today's price is not included
    when determining today's previous resistance.
    """
    df = df.copy()
    high = df["High"]
    close = df["Close"]

    df["HIGH20_PREVIOUS"] = high.rolling(20).max().shift(1)
    df["HIGH50_PREVIOUS"] = high.rolling(50).max().shift(1)
    df["HIGH100_PREVIOUS"] = high.rolling(100).max().shift(1)

    df["DIST_HIGH20"] = (
        (df["HIGH20_PREVIOUS"] - close) / close
    )
    df["DIST_HIGH50"] = (
        (df["HIGH50_PREVIOUS"] - close) / close
    )

    return df


def calculate_price_momentum(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate 5D, 20D and 60D returns."""
    df = df.copy()
    close = df["Close"]

    df["RETURN_5D"] = close.pct_change(5)
    df["RETURN_20D"] = close.pct_change(20)
    df["RETURN_60D"] = close.pct_change(60)

    return df


def calculate_ma_slopes(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate moving-average slopes."""
    df = df.copy()

    # These calculations require the moving averages.
    if "SMA20" not in df.columns or "SMA50" not in df.columns:
        df = calculate_moving_averages(df)

    df["SMA20_SLOPE"] = df["SMA20"].pct_change(10)
    df["SMA50_SLOPE"] = df["SMA50"].pct_change(20)

    return df


def calculate_volatility(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate 20/50-day volatility and their ratio."""
    df = df.copy()
    daily_returns = df["Close"].pct_change()

    df["VOLATILITY_20"] = daily_returns.rolling(20).std()
    df["VOLATILITY_50"] = daily_returns.rolling(50).std()
    df["VOLATILITY_RATIO"] = (
        df["VOLATILITY_20"] / df["VOLATILITY_50"]
    )

    return df


# Calculation delegates.
# Add/remove calculation methods here if you want direct control
# over the calculations. Normally ACTIVE_INDICATORS below is enough.
CALCULATOR_DELEGATES: dict[str, Callable[[pd.DataFrame], pd.DataFrame]] = {
    "moving_averages": calculate_moving_averages,
    "rsi": calculate_rsi,
    "macd": calculate_macd,
    "atr": calculate_atr,
    "adx": calculate_adx,
    "bollinger_bands": calculate_bollinger_bands,
    "volume": calculate_volume,
    "resistance": calculate_resistance,
    "price_momentum": calculate_price_momentum,
    "ma_slopes": calculate_ma_slopes,
    "volatility": calculate_volatility,
}


def calculate_selected_indicators(
    df: pd.DataFrame,
    indicators: Iterable[IndicatorDefinition],
) -> pd.DataFrame:
    """
    Execute only the calculator delegates required by `indicators`.

    Each calculator is executed at most once, even if several
    scoring indicators depend on it.
    """
    df = df.copy()

    required_calculators = []
    for indicator in indicators:
        for calculator_name in indicator.calculator_names:
            if calculator_name not in required_calculators:
                required_calculators.append(calculator_name)

    for calculator_name in required_calculators:
        calculator = CALCULATOR_DELEGATES[calculator_name]
        df = calculator(df)

    return df


# ============================================================
# SCORING DELEGATES
#
# Each scoring method is now independent. This makes it easy to
# enable/disable indicators without changing the main scoring loop.
# ============================================================

def score_price_above_sma200(df):
    latest = df.iloc[-1]
    if latest["Close"] > latest["SMA200"]:
        return 8, ["Price above SMA200"], []
    return 0, [], []


def score_price_above_sma50(df):
    latest = df.iloc[-1]
    if latest["Close"] > latest["SMA50"]:
        return 7, ["Price above SMA50"], []
    return 0, [], []


def score_ma_structure(df):
    latest = df.iloc[-1]
    if latest["SMA20"] > latest["SMA50"] > latest["SMA200"]:
        return 10, ["SMA20 > SMA50 > SMA200"], []
    return 0, [], []


def score_sma20_slope(df):
    latest = df.iloc[-1]
    if latest["SMA20_SLOPE"] > 0.01:
        return 5, ["SMA20 rising"], []
    return 0, [], []


def score_sma50_slope(df):
    latest = df.iloc[-1]
    if latest["SMA50_SLOPE"] > 0:
        return 5, ["SMA50 rising"], []
    return 0, [], []


def score_near_20_day_resistance(df):
    latest = df.iloc[-1]
    distance = latest["DIST_HIGH20"]

    if 0 <= distance < 0.03:
        return 8, ["Within 3% of 20-day high"], []

    if 0 <= distance < RESISTANCE_DISTANCE:
        return 5, ["Within 5% of 20-day high"], []

    return 0, [], []


def score_near_50_day_resistance(df):
    latest = df.iloc[-1]
    distance = latest["DIST_HIGH50"]

    if 0 <= distance < 0.03:
        return 10, ["Within 3% of 50-day high"], []

    if 0 <= distance < RESISTANCE_DISTANCE:
        return 6, ["Within 5% of 50-day high"], []

    return 0, [], []


def score_rsi(df):
    latest = df.iloc[-1]
    rsi = latest["RSI"]

    if 55 <= rsi <= 70:
        return 6, ["Healthy bullish RSI"], []

    if 50 <= rsi < 55:
        return 3, ["Positive RSI"], []

    if rsi > 75:
        return 0, [], ["RSI potentially overbought"]

    return 0, [], []


def score_macd(df):
    latest = df.iloc[-1]

    if latest["MACD"] > latest["MACD_SIGNAL"]:
        return 6, ["MACD bullish"], []

    return 0, [], []


def score_macd_histogram(df):
    latest = df.iloc[-1]

    if latest["MACD_HIST"] > 0:
        return 3, ["Positive MACD histogram"], []

    return 0, [], []


def score_adx(df):
    latest = df.iloc[-1]
    adx = latest["ADX"]

    if adx >= 25:
        return 7, ["Strong trend (ADX > 25)"], []

    if adx >= 20:
        return 3, ["Moderate trend"], []

    return 0, [], []


def score_directional_movement(df):
    latest = df.iloc[-1]

    if latest["DI_PLUS"] > latest["DI_MINUS"]:
        return 4, ["Positive directional movement"], []

    return 0, [], []


def score_volume_consolidation(df):
    latest = df.iloc[-1]

    if latest["VOL5"] < latest["VOL50"]:
        return 4, ["Volume contracting"], []

    return 0, [], []


def score_volatility_contraction(df):
    latest = df.iloc[-1]

    if latest["VOLATILITY_RATIO"] < 0.85:
        return 6, ["Volatility contracting"], []

    return 0, [], []


def score_atr_contraction(df):
    atr_10 = df["ATR"].rolling(10).mean().iloc[-1]
    atr_50 = df["ATR"].rolling(50).mean().iloc[-1]

    if atr_10 < atr_50:
        return 3, ["ATR contracting"], []

    return 0, [], []


def score_bollinger_compression(df):
    latest = df.iloc[-1]

    bb_width_median = (
        df["BB_WIDTH"].rolling(100).median().iloc[-1]
    )

    if latest["BB_WIDTH"] < bb_width_median:
        return 4, ["Bollinger Bands compressed"], []

    return 0, [], []


def score_recent_performance(df):
    latest = df.iloc[-1]

    if latest["RETURN_20D"] > 0:
        return 3, ["Positive 20-day momentum"], []

    return 0, [], []


def score_liquidity(df):
    latest = df.iloc[-1]

    if latest["AVG_DOLLAR_VOLUME_20"] >= MIN_AVG_DOLLAR_VOLUME:
        return 3, ["Good liquidity"], []

    return 0, [], []


# ============================================================
# AVAILABLE SCORING INDICATORS
#
# This is the main "delegate list" you can customize.
#
# Example:
#
# ACTIVE_INDICATORS = [
#     INDICATORS["trend_sma200"],
#     INDICATORS["rsi"],
#     INDICATORS["macd"],
# ]
#
# The scanner will then calculate only the technical data required
# by these selected indicators.
# ============================================================

INDICATORS: dict[str, IndicatorDefinition] = {
    "trend_sma200": IndicatorDefinition(
        name="Price above SMA200",
        calculator_names=("moving_averages",),
        scorer=score_price_above_sma200,
        max_points=8,
    ),
    "trend_sma50": IndicatorDefinition(
        name="Price above SMA50",
        calculator_names=("moving_averages",),
        scorer=score_price_above_sma50,
        max_points=7,
    ),
    "ma_structure": IndicatorDefinition(
        name="Moving average structure",
        calculator_names=("moving_averages",),
        scorer=score_ma_structure,
        max_points=10,
    ),
    "sma20_slope": IndicatorDefinition(
        name="SMA20 slope",
        calculator_names=("moving_averages", "ma_slopes"),
        scorer=score_sma20_slope,
        max_points=5,
    ),
    "sma50_slope": IndicatorDefinition(
        name="SMA50 slope",
        calculator_names=("moving_averages", "ma_slopes"),
        scorer=score_sma50_slope,
        max_points=5,
    ),
    "resistance20": IndicatorDefinition(
        name="20-day resistance",
        calculator_names=("resistance",),
        scorer=score_near_20_day_resistance,
        max_points=8,
    ),
    "resistance50": IndicatorDefinition(
        name="50-day resistance",
        calculator_names=("resistance",),
        scorer=score_near_50_day_resistance,
        max_points=10,
    ),
    "rsi": IndicatorDefinition(
        name="RSI",
        calculator_names=("rsi",),
        scorer=score_rsi,
        max_points=6,
    ),
    "macd": IndicatorDefinition(
        name="MACD",
        calculator_names=("macd",),
        scorer=score_macd,
        max_points=6,
    ),
    "macd_histogram": IndicatorDefinition(
        name="MACD histogram",
        calculator_names=("macd",),
        scorer=score_macd_histogram,
        max_points=3,
    ),
    "adx": IndicatorDefinition(
        name="ADX",
        calculator_names=("adx",),
        scorer=score_adx,
        max_points=7,
    ),
    "directional_movement": IndicatorDefinition(
        name="+DI vs -DI",
        calculator_names=("adx",),
        scorer=score_directional_movement,
        max_points=4,
    ),
    "volume_consolidation": IndicatorDefinition(
        name="Volume consolidation",
        calculator_names=("volume",),
        scorer=score_volume_consolidation,
        max_points=4,
    ),
    "volatility_contraction": IndicatorDefinition(
        name="Volatility contraction",
        calculator_names=("volatility",),
        scorer=score_volatility_contraction,
        max_points=6,
    ),
    "atr_contraction": IndicatorDefinition(
        name="ATR contraction",
        calculator_names=("atr",),
        scorer=score_atr_contraction,
        max_points=3,
    ),
    "bollinger_compression": IndicatorDefinition(
        name="Bollinger Band compression",
        calculator_names=("bollinger_bands",),
        scorer=score_bollinger_compression,
        max_points=4,
    ),
    "recent_performance": IndicatorDefinition(
        name="Recent performance",
        calculator_names=("price_momentum",),
        scorer=score_recent_performance,
        max_points=3,
    ),
    "liquidity": IndicatorDefinition(
        name="Liquidity",
        calculator_names=("volume",),
        scorer=score_liquidity,
        max_points=3,
    ),
}


# Select the indicators you want to use.
#
# By default, all indicators are enabled, preserving the behavior
# of the original scanner (apart from making the score relative to
# the selected indicators; see calculate_breakout_score()).
ACTIVE_INDICATORS = list(INDICATORS.values())


def calculate_breakout_score(
    df: pd.DataFrame,
    indicators: Iterable[IndicatorDefinition] | None = None,
) -> tuple[int, list[str], list[str]]:
    """
    Calculate a normalized 0-100 score using the selected indicators.

    The original script had 18 scoring rules whose raw maximum adds
    up to 102 points. With a delegate list, normalization is useful:
    selecting a subset of indicators still produces a meaningful
    0-100 score.

    The returned score is rounded to the nearest integer.
    """
    if indicators is None:
        indicators = ACTIVE_INDICATORS

    indicators = list(indicators)

    if not indicators:
        return 0, [], ["No scoring indicators selected"]

    score = 0.0
    max_score = sum(indicator.max_points for indicator in indicators)

    reasons: list[str] = []
    warnings_list: list[str] = []

    for indicator in indicators:
        points, indicator_reasons, indicator_warnings = (
            indicator.scorer(df)
        )

        score += points
        reasons.extend(indicator_reasons)
        warnings_list.extend(indicator_warnings)

    normalized_score = 100 * score / max_score if max_score else 0

    return round(min(normalized_score, 100)), reasons, warnings_list


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
