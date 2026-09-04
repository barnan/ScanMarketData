"""Market and sector context calculations for sector-aware scanning."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import pandas as pd


@dataclass(frozen=True)
class ContextSnapshot:
    """Point-in-time context values calculated only from data through ``as_of``."""

    as_of: pd.Timestamp
    values: dict[str, float]
    score: float
    warnings: tuple[str, ...] = ()


def _close(frame: pd.DataFrame) -> pd.Series:
    if "Close" not in frame.columns:
        raise ValueError("Context data must contain a Close column")
    close = frame["Close"].dropna().astype(float)
    close.index = pd.to_datetime(close.index).tz_localize(None).normalize()
    return close[~close.index.duplicated(keep="last")].sort_index()


def _latest_at(close: pd.Series, as_of: pd.Timestamp) -> pd.Series:
    return close.loc[close.index <= as_of]


def _trend_values(frame: pd.DataFrame, as_of: pd.Timestamp) -> dict[str, float]:
    close = _latest_at(_close(frame), as_of)
    if len(close) < 200:
        raise ValueError("At least 200 observations are required for context trend")

    sma50 = close.rolling(50).mean()
    sma200 = close.rolling(200).mean()
    latest = float(close.iloc[-1])
    return {
        "close": latest,
        "sma50": float(sma50.iloc[-1]),
        "sma200": float(sma200.iloc[-1]),
        "return20": float(close.iloc[-1] / close.iloc[-21] - 1),
        "sma50_slope20": float(sma50.iloc[-1] / sma50.iloc[-21] - 1),
    }


def calculate_market_context(
    frames: Mapping[str, pd.DataFrame],
    as_of: str | pd.Timestamp,
) -> ContextSnapshot:
    """Score broad-market conditions from named benchmark frames.

    Expected names are ``sp500``, ``vix``, ``dxy`` and optionally ``real_yield``.
    Missing optional series produce warnings rather than look-ahead-prone defaults.
    """
    evaluation_date = pd.Timestamp(as_of).normalize()
    values: dict[str, float] = {}
    warnings: list[str] = []

    sp500 = _trend_values(frames["sp500"], evaluation_date)
    values.update({f"sp500_{key}": value for key, value in sp500.items()})
    score = 0.0
    if sp500["close"] > sp500["sma200"]:
        score += 2
    if sp500["sma50_slope20"] > 0:
        score += 2
    if sp500["return20"] > 0:
        score += 1

    if "vix" in frames:
        vix = _latest_at(_close(frames["vix"]), evaluation_date)
        if len(vix) >= 20:
            vix_sma20 = vix.rolling(20).mean().iloc[-1]
            values["vix"] = float(vix.iloc[-1])
            values["vix_sma20"] = float(vix_sma20)
            if vix.iloc[-1] <= vix_sma20:
                score += 2
        else:
            warnings.append("Insufficient VIX history")
    else:
        warnings.append("VIX context unavailable")

    if "dxy" in frames:
        dxy = _trend_values(frames["dxy"], evaluation_date)
        values["dxy_return20"] = dxy["return20"]
        if dxy["return20"] <= 0:
            score += 2
    else:
        warnings.append("DXY context unavailable")

    if "real_yield" in frames:
        real_yield = _latest_at(_close(frames["real_yield"]), evaluation_date)
        if len(real_yield) >= 21:
            values["real_yield_change20"] = float(real_yield.iloc[-1] - real_yield.iloc[-21])
            if values["real_yield_change20"] <= 0:
                score += 2
        else:
            warnings.append("Insufficient real-yield history")
    else:
        warnings.append("Real-yield context unavailable")

    return ContextSnapshot(evaluation_date, values, min(score, 9), tuple(warnings))


def calculate_sector_context(
    frames: Mapping[str, pd.DataFrame],
    as_of: str | pd.Timestamp,
    breadth_frames: Mapping[str, pd.DataFrame] | None = None,
) -> ContextSnapshot:
    """Score gold, silver, mining and relative-strength conditions."""
    evaluation_date = pd.Timestamp(as_of).normalize()
    values: dict[str, float] = {}
    warnings: list[str] = []
    score = 0.0

    for name in ("gold", "silver", "gdx", "gdxj", "slv"):
        if name not in frames:
            warnings.append(f"{name} context unavailable")
            continue
        trend = _trend_values(frames[name], evaluation_date)
        values[f"{name}_return20"] = trend["return20"]
        values[f"{name}_sma50_slope20"] = trend["sma50_slope20"]
        values[f"{name}_above_sma200"] = float(trend["close"] > trend["sma200"])
        if trend["close"] > trend["sma200"]:
            score += 1
        if trend["sma50_slope20"] > 0:
            score += 1

    if "gdx" in frames and "gold" in frames:
        gdx_return = values.get("gdx_return20")
        gold_return = values.get("gold_return20")
        values["gdx_relative_gold20"] = gdx_return - gold_return
        if values["gdx_relative_gold20"] > 0:
            score += 2

    if "gold" in frames and "silver" in frames:
        gold = _latest_at(_close(frames["gold"]), evaluation_date)
        silver = _latest_at(_close(frames["silver"]), evaluation_date)
        joined = pd.concat({"gold": gold, "silver": silver}, axis=1).dropna()
        if len(joined) >= 21:
            ratio = joined["gold"] / joined["silver"]
            values["gold_silver_ratio_change20"] = float(ratio.iloc[-1] / ratio.iloc[-21] - 1)

    if breadth_frames:
        breadth_values = []
        for frame in breadth_frames.values():
            close = _latest_at(_close(frame), evaluation_date)
            if len(close) >= 50:
                breadth_values.append(float(close.iloc[-1] > close.rolling(50).mean().iloc[-1]))
        if breadth_values:
            values["sector_breadth50"] = sum(breadth_values) / len(breadth_values)
            if values["sector_breadth50"] >= 0.5:
                score += 3
        else:
            warnings.append("Insufficient sector breadth history")

    return ContextSnapshot(evaluation_date, values, min(score, 15), tuple(warnings))
