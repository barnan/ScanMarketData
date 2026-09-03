"""Scoring for the rising-support-line indicator."""
from __future__ import annotations

from typing import Any

import pandas as pd


def _get(parameters: dict[str, Any] | None, key: str, default: Any) -> Any:
    return (parameters or {}).get(key, default)


def score_rising_support_line(
    df: pd.DataFrame,
    max_points: float,
    parameters: dict[str, Any] | None = None,
) -> tuple[float, list[str], list[str]]:
    """Score the quality of a rising support-line setup.

    The score rewards:
      - a valid rising support line,
      - enough support touches,
      - price remaining above the line,
      - current price being reasonably close to support.

    The function returns a score from 0 to `max_points`.
    """
    latest = df.iloc[-1]

    min_touches = int(_get(parameters, "min_touches", 3))
    ideal_touch_count = int(_get(parameters, "ideal_touch_count", 4))
    max_current_distance_pct = float(
        _get(parameters, "max_current_distance_pct", 0.04)
    )
    ideal_current_distance_pct = float(
        _get(parameters, "ideal_current_distance_pct", 0.02)
    )

    valid = bool(latest.get("SUPPORT_VALID", False))
    rising = bool(latest.get("SUPPORT_IS_RISING", False))
    all_above = bool(latest.get("SUPPORT_ALL_ABOVE", False))
    touches = int(latest.get("SUPPORT_TOUCH_COUNT", 0) or 0)
    current_distance = float(
        latest.get("SUPPORT_DISTANCE_PCT", float("nan"))
    )

    if not valid or not rising or not all_above:
        return 0, [], ["No valid rising support line"]

    if touches < min_touches:
        return 0, [], [
            f"Support line has only {touches} touches "
            f"(minimum {min_touches})"
        ]

    if pd.isna(current_distance) or current_distance < 0:
        return 0, [], ["Invalid current support distance"]

    # Touch quality: reaches 100% of this component at ideal_touch_count.
    touch_factor = min(touches / max(ideal_touch_count, 1), 1.0)

    # Proximity quality: 100% at the ideal distance, 0% at max distance.
    if current_distance <= ideal_current_distance_pct:
        proximity_factor = 1.0
    elif current_distance >= max_current_distance_pct:
        proximity_factor = 0.0
    else:
        proximity_factor = (
            max_current_distance_pct - current_distance
        ) / (
            max_current_distance_pct - ideal_current_distance_pct
        )

    # Weight the two geometric properties equally.
    score = max_points * (0.5 * touch_factor + 0.5 * proximity_factor)

    reasons = [
        f"Rising support line with {touches} touches",
        f"Close is {current_distance:.1%} above support",
    ]

    return round(score, 2), reasons, []
