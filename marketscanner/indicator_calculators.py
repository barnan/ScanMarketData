
import pandas as pd

from ta.trend import SMAIndicator, EMAIndicator, MACD, ADXIndicator
from ta.momentum import RSIIndicator
from ta.volatility import AverageTrueRange, BollingerBands
from typing import Callable, Iterable

from .indicator_definition import *
from .support_line_calculator import calculate_rising_support_line


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

    df["DIST_HIGH20"] = ((df["HIGH20_PREVIOUS"] - close) / close)
    df["DIST_HIGH50"] = ((df["HIGH50_PREVIOUS"] - close) / close)

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
    df["VOLATILITY_RATIO"] = (df["VOLATILITY_20"] / df["VOLATILITY_50"])

    return df

def calculate_horizontal_support(df: pd.DataFrame) -> pd.DataFrame:
    """Estimate recent horizontal support from local lows."""
    df = df.copy()
    tolerance = 0.03
    lows = df["Low"].rolling(3, center=True).min()
    pivot_mask = df["Low"].eq(lows)
    pivot_values = df.loc[pivot_mask, "Low"].tail(60)

    support = float("nan")
    touches = 0
    if len(pivot_values) >= 2:
        candidates = pivot_values.to_numpy(dtype=float)
        for candidate in candidates:
            clustered = abs(candidates / candidate - 1) <= tolerance
            if int(clustered.sum()) > touches:
                touches = int(clustered.sum())
                support = float(candidates[clustered].mean())

    df["HORIZONTAL_SUPPORT"] = support
    df["HORIZONTAL_SUPPORT_TOUCHES"] = touches
    df["HORIZONTAL_SUPPORT_DISTANCE_PCT"] = (
        df["Close"] / support - 1 if pd.notna(support) else float("nan")
    )
    df["HORIZONTAL_SUPPORT_HOLDS"] = (
        df["Close"] >= support * (1 - tolerance)
        if pd.notna(support)
        else False
    )
    return df

def calculate_triangle_compression(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate converging-envelope geometry for a triangle setup."""
    df = df.copy()
    lookback = 60
    window = df.tail(lookback)
    if len(window) < lookback:
        df["TRIANGLE_VALID"] = False
        df["TRIANGLE_NEAR_SUPPORT"] = False
        return df

    x = pd.Series(range(len(window)), dtype=float)
    high_values = pd.Series(window["High"].to_numpy(dtype=float))
    low_values = pd.Series(window["Low"].to_numpy(dtype=float))
    high_slope = float(high_values.corr(x))
    low_slope = float(low_values.corr(x))
    high_start = float(window["High"].head(10).mean())
    high_end = float(window["High"].tail(10).mean())
    low_start = float(window["Low"].head(10).mean())
    low_end = float(window["Low"].tail(10).mean())
    initial_width = high_start - low_start
    current_width = high_end - low_end
    width_ratio = current_width / initial_width if initial_width > 0 else float("nan")

    df["TRIANGLE_HIGH_SLOPE"] = high_slope
    df["TRIANGLE_LOW_SLOPE"] = low_slope
    df["TRIANGLE_WIDTH_RATIO"] = width_ratio
    df["TRIANGLE_VALID"] = bool(
        pd.notna(width_ratio)
        and high_slope < 0
        and low_slope > 0
        and width_ratio <= 0.8
    )
    df["TRIANGLE_NEAR_SUPPORT"] = bool(
        pd.notna(width_ratio)
        and current_width > 0
        and (float(window["Close"].iloc[-1]) - low_end) / current_width <= 0.4
    )
    return df

def calculate_breakout_retest(df: pd.DataFrame) -> pd.DataFrame:
    """Detect a prior resistance breakout followed by a current retest."""
    df = df.copy()
    resistance = df["High"].rolling(20).max().shift(1)
    breakout = df["Close"] > resistance * 1.005
    latest_breakout = breakout.where(breakout).last_valid_index()
    is_retest = False
    if latest_breakout is not None:
        breakout_position = df.index.get_loc(latest_breakout)
        bars_since = len(df) - 1 - breakout_position
        level = resistance.loc[latest_breakout]
        distance = df["Close"].iloc[-1] / level - 1
        is_retest = (
            2 <= bars_since <= 20
            and -0.02 <= float(distance) <= 0.03
        )

    df["BREAKOUT_RETEST"] = is_retest
    df["BREAKOUT_LEVEL"] = resistance.where(breakout).ffill()
    df["BREAKOUT_RETEST_DISTANCE"] = (
        df["Close"] / df["BREAKOUT_LEVEL"] - 1
    )
    return df


# Calculation delegates.
# Add/remove calculation methods here if you want direct control
# over the calculations. Normally DEFAULT_INDICATORS below is enough.
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
    "horizontal_support": calculate_horizontal_support,
    "triangle_compression": calculate_triangle_compression,
    "breakout_retest": calculate_breakout_retest,
    "rising_support_line": calculate_rising_support_line
}


def calculate_selected_indicators(
    df: pd.DataFrame,
    indicators: Iterable[IndicatorDefinition],
    as_of: str | pd.Timestamp | None = None,
) -> pd.DataFrame:
    """
    Execute only the calculator delegates required by `indicators`.

    Each calculator is executed at most once, even if several
    scoring indicators depend on it.

    When ``as_of`` is supplied, rows after that date are removed before
    any calculator runs. This keeps every derived feature point-in-time.
    """
    df = df.copy()
    if as_of is not None:
        evaluation_date = pd.Timestamp(as_of).normalize()
        index = pd.to_datetime(df.index)
        if getattr(index, "tz", None) is not None:
            index = index.tz_localize(None)
        df = df.loc[index.normalize() <= evaluation_date]

    if df.empty:
        raise ValueError("No market data is available on or before as_of")

    required_calculators = []
    for indicator in indicators:
        for calculator_name in indicator.calculator_names:
            if calculator_name not in required_calculators:
                required_calculators.append(calculator_name)

    for calculator_name in required_calculators:
        calculator = CALCULATOR_DELEGATES[calculator_name]
        df = calculator(df)

    return df
