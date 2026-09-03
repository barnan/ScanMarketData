"""Support-line calculations for the bullish pre-breakout scanner.

The calculator finds a rising straight support line over a configurable
lookback window. By construction, the selected line is never above the
observed price series.

Default source is Close, because the requested condition is that all
closing values remain above the support line. The source can be changed
to Low when wick-based support is preferred.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .supportline_definition import SupportLineParameters


# helper methods are private to this module, so they are prefixed with an underscore *****************************

def _candidate_slopes(values: np.ndarray) -> np.ndarray:
    """Return positive pairwise slopes from the observed price series."""
    n = len(values)
    slopes: list[float] = []

    for i in range(n - 1):
        for j in range(i + 1, n):
            slope = (values[j] - values[i]) / (j - i)
            if slope > 0:
                slopes.append(float(slope))

    if not slopes:
        return np.array([], dtype=float)

    return np.unique(np.asarray(slopes))


def _touch_indices(
    distances_pct: np.ndarray,
    tolerance_pct: float,
    min_separation: int,
) -> list[int]:
    """Select reasonably separated points that touch the support line."""
    candidates = np.flatnonzero(distances_pct <= tolerance_pct)

    selected: list[int] = []
    for idx in candidates:
        if not selected or idx - selected[-1] >= min_separation:
            selected.append(int(idx))

    return selected

# main calculator function is public and is called by the scanner *********************************************************

def calculate_rising_support_line(
    df: pd.DataFrame,
    parameters: SupportLineParameters | None = None,
) -> pd.DataFrame:
    """Calculate a rising support line and its quality metrics.

    The selected line is:

        S(x) = intercept + slope * x

    with slope > 0 and S(x) <= price(x) for every point in the lookback.

    Among candidate positive slopes, the line minimizing the mean percentage
    distance between price and support is selected, subject to the minimum
    slope. This creates a lower-envelope style support line rather than an
    ordinary regression line, which could cross above the prices.
    """
    p = parameters or SupportLineParameters()
    if p.lookback < 3:
        raise ValueError("Support lookback must be at least 3.")
    if p.min_touches < 1:
        raise ValueError("min_touches must be at least 1.")
    if p.touch_tolerance_pct < 0:
        raise ValueError("touch_tolerance_pct cannot be negative.")

    result = df.copy()

    required = {p.source_column}
    missing = required - set(result.columns)
    if missing:
        raise ValueError(f"Missing support-line columns: {sorted(missing)}")

    n = len(result)
    if n < p.lookback:
        # Add columns so downstream code can safely inspect them.
        for column in (
            "SUPPORT_SLOPE",
            "SUPPORT_INTERCEPT",
            "SUPPORT_VALUE",
            "SUPPORT_DISTANCE_PCT",
            "SUPPORT_MIN_DISTANCE_PCT",
            "SUPPORT_AVG_DISTANCE_PCT",
            "SUPPORT_MAX_DISTANCE_PCT",
            "SUPPORT_TOUCH_COUNT",
            "SUPPORT_ALL_ABOVE",
            "SUPPORT_IS_RISING",
            "SUPPORT_VALID",
        ):
            result[column] = np.nan
        return result

    window = result.iloc[-p.lookback:].copy()
    values = window[p.source_column].astype(float).to_numpy()

    if not np.isfinite(values).all() or np.any(values <= 0):
        raise ValueError("Support-line source contains invalid/non-positive values.")

    x = np.arange(len(values), dtype=float)
    slopes = _candidate_slopes(values)

    min_slope_abs = p.min_slope_pct_per_day * float(values[-1])

    if slopes.size == 0:
        valid = False
        slope = np.nan
        intercept = np.nan
        line = np.full(len(values), np.nan)
    else:
        slopes = slopes[slopes >= min_slope_abs]

        if slopes.size == 0:
            valid = False
            slope = np.nan
            intercept = np.nan
            line = np.full(len(values), np.nan)
        else:
            candidates = []

            # For a fixed slope, the largest feasible intercept is:
            # min(price - slope*x). This guarantees line <= price everywhere.
            for candidate_slope in slopes:
                candidate_intercept = float(
                    np.min(values - candidate_slope * x)
                )
                candidate_line = (
                    candidate_intercept + candidate_slope * x
                )
                distances_pct = (
                    (values - candidate_line) / values
                )

                touches = _touch_indices(
                    distances_pct,
                    p.touch_tolerance_pct,
                    p.min_touch_separation,
                )

                mean_distance = float(np.mean(distances_pct))
                candidates.append(
                    (
                        len(touches),
                        mean_distance,
                        candidate_slope,
                        candidate_intercept,
                        candidate_line,
                    )
                )

            # Prefer lines with more meaningful touches; among equally
            # supported lines, prefer the line closest to price.
            candidates.sort(key=lambda item: (-item[0], item[1], -item[2]))
            _, _, slope, intercept, line = candidates[0]
            valid = True

    if valid:
        distances_pct = (values - line) / values
        touches = _touch_indices(
            distances_pct,
            p.touch_tolerance_pct,
            p.min_touch_separation,
        )
        all_above = bool(np.all(values >= line - 1e-12))
        touch_count = len(touches)
        min_distance = float(np.min(distances_pct))
        avg_distance = float(np.mean(distances_pct))
        max_distance = float(np.max(distances_pct))
    else:
        distances_pct = np.full(len(values), np.nan)
        touches = []
        all_above = False
        touch_count = 0
        min_distance = np.nan
        avg_distance = np.nan
        max_distance = np.nan

    # Only the latest row needs the summary values. This keeps the
    # calculator inexpensive and makes it easy for a scorer to inspect.
    result["SUPPORT_SLOPE"] = np.nan
    result["SUPPORT_INTERCEPT"] = np.nan
    result["SUPPORT_VALUE"] = np.nan
    result["SUPPORT_DISTANCE_PCT"] = np.nan
    result["SUPPORT_MIN_DISTANCE_PCT"] = np.nan
    result["SUPPORT_AVG_DISTANCE_PCT"] = np.nan
    result["SUPPORT_MAX_DISTANCE_PCT"] = np.nan
    result["SUPPORT_TOUCH_COUNT"] = np.nan
    result["SUPPORT_ALL_ABOVE"] = np.nan
    result["SUPPORT_IS_RISING"] = np.nan
    result["SUPPORT_VALID"] = np.nan

    last_index = result.index[-1]
    result.at[last_index, "SUPPORT_SLOPE"] = slope
    result.at[last_index, "SUPPORT_INTERCEPT"] = intercept
    result.at[last_index, "SUPPORT_VALUE"] = line[-1] if valid else np.nan
    result.at[last_index, "SUPPORT_DISTANCE_PCT"] = (
        distances_pct[-1] if valid else np.nan
    )
    result.at[last_index, "SUPPORT_MIN_DISTANCE_PCT"] = min_distance
    result.at[last_index, "SUPPORT_AVG_DISTANCE_PCT"] = avg_distance
    result.at[last_index, "SUPPORT_MAX_DISTANCE_PCT"] = max_distance
    result.at[last_index, "SUPPORT_TOUCH_COUNT"] = touch_count
    result.at[last_index, "SUPPORT_ALL_ABOVE"] = all_above
    result.at[last_index, "SUPPORT_IS_RISING"] = bool(valid and slope > 0)
    result.at[last_index, "SUPPORT_VALID"] = bool(
        valid
        and all_above
        and touch_count >= p.min_touches
    )

    return result
