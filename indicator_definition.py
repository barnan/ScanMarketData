
import pandas as pd

from dataclasses import dataclass
from typing import Callable

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
