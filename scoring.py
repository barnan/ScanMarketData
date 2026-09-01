
import pandas as pd

from typing import Iterable

from indicator_definition import *
from scoring_support_line import score_rising_support_line


# How close should price be to resistance?
RESISTANCE_DISTANCE = 0.05  # 5%
MIN_PRICE = 1.0                             # GPT -> 5.0
MIN_AVG_DOLLAR_VOLUME = 1_000               # GPT -> 1_000_000

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
        parameters=None,
    ),
    "trend_sma50": IndicatorDefinition(
        name="Price above SMA50",
        calculator_names=("moving_averages",),
        scorer=score_price_above_sma50,
        max_points=7,
        parameters=None,
    ),
    "ma_structure": IndicatorDefinition(
        name="Moving average structure",
        calculator_names=("moving_averages",),
        scorer=score_ma_structure,
        max_points=10,
        parameters=None,
    ),
    "sma20_slope": IndicatorDefinition(
        name="SMA20 slope",
        calculator_names=("moving_averages", "ma_slopes"),
        scorer=score_sma20_slope,
        max_points=5,
        parameters=None,
    ),
    "sma50_slope": IndicatorDefinition(
        name="SMA50 slope",
        calculator_names=("moving_averages", "ma_slopes"),
        scorer=score_sma50_slope,
        max_points=5,
        parameters=None,
    ),
    "resistance20": IndicatorDefinition(
        name="20-day resistance",
        calculator_names=("resistance",),
        scorer=score_near_20_day_resistance,
        max_points=8,
        parameters=None,
    ),
    "resistance50": IndicatorDefinition(
        name="50-day resistance",
        calculator_names=("resistance",),
        scorer=score_near_50_day_resistance,
        max_points=10,
        parameters=None,
    ),
    "rsi": IndicatorDefinition(
        name="RSI",
        calculator_names=("rsi",),
        scorer=score_rsi,
        max_points=6,
        parameters=None,
    ),
    "macd": IndicatorDefinition(
        name="MACD",
        calculator_names=("macd",),
        scorer=score_macd,
        max_points=6,
        parameters=None,
    ),
    "macd_histogram": IndicatorDefinition(
        name="MACD histogram",
        calculator_names=("macd",),
        scorer=score_macd_histogram,
        max_points=3,
        parameters=None,
    ),
    "adx": IndicatorDefinition(
        name="ADX",
        calculator_names=("adx",),
        scorer=score_adx,
        max_points=7,
        parameters=None,
    ),
    "directional_movement": IndicatorDefinition(
        name="+DI vs -DI",
        calculator_names=("adx",),
        scorer=score_directional_movement,
        max_points=4,
        parameters=None,
    ),
    "volume_consolidation": IndicatorDefinition(
        name="Volume consolidation",
        calculator_names=("volume",),
        scorer=score_volume_consolidation,
        max_points=4,
        parameters=None,
    ),
    "volatility_contraction": IndicatorDefinition(
        name="Volatility contraction",
        calculator_names=("volatility",),
        scorer=score_volatility_contraction,
        max_points=6,
        parameters=None,
    ),
    "atr_contraction": IndicatorDefinition(
        name="ATR contraction",
        calculator_names=("atr",),
        scorer=score_atr_contraction,
        max_points=3,
        parameters=None,
    ),
    "bollinger_compression": IndicatorDefinition(
        name="Bollinger Band compression",
        calculator_names=("bollinger_bands",),
        scorer=score_bollinger_compression,
        max_points=4,
        parameters=None,
    ),
    "recent_performance": IndicatorDefinition(
        name="Recent performance",
        calculator_names=("price_momentum",),
        scorer=score_recent_performance,
        max_points=3,
        parameters=None,
    ),
    "liquidity": IndicatorDefinition(
        name="Liquidity",
        calculator_names=("volume",),
        scorer=score_liquidity,
        max_points=3,
        parameters=None,
    ),
    "rising_support_line": IndicatorDefinition(
        name="Rising support line",
        calculator_names=("rising_support_line",),
        scorer=score_rising_support_line,
        max_points=10,
        parameters={
            "lookback": 40,
            "source_column": "Close",
            "min_slope_pct_per_day": 0.0001,
            "touch_tolerance_pct": 0.01,
            "min_touches": 3,
            "min_touch_separation": 3,
            "weight": 10,
            "ideal_touch_count": 4,
            "ideal_current_distance_pct": 0.02,
            "max_current_distance_pct": 0.04,
        },
    )
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

