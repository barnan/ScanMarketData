
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
    "rising_support_line": calculate_rising_support_line
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
