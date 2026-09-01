
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class SupportLineParameters:
    """Parameters controlling support-line detection."""

    lookback: int = 40
    source_column: Literal["Close", "Low"] = "Close"

    # Minimum slope expressed as a fraction of current price per day.
    # Example: 0.001 means roughly +0.10% of current price per day.
    min_slope_pct_per_day: float = 0.0001

    # A point is a touch when it is within this percentage above the line.
    touch_tolerance_pct: float = 0.05    # chatGPT -> 0.01

    # Require at least this many touches.
    min_touches: int = 3

    # Optional minimum temporal separation between touches.
    min_touch_separation: int = 3

