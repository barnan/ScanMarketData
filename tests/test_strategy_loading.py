from pathlib import Path

import numpy as np
import pandas as pd

from marketscanner.strategy_loader import (
    load_strategy,
    resolve_indicators_for_strategy,
)
from marketscanner.indicator_calculators import calculate_selected_indicators


ROOT = Path(__file__).resolve().parent.parent


def test_strategy_file_loads_active_indicator_selection_only():
    strategy = load_strategy(
        ROOT / "marketscanner" / "strategies" / "pre_breakout_with_support.json"
    )

    assert strategy.name == "Pre-breakout with rising support"
    assert "rising_support_line" in strategy.active_indicators
    assert strategy.indicator_overrides == {}

    indicators = resolve_indicators_for_strategy(strategy)
    support = next(ind for ind in indicators if ind.name == "Rising support line")

    assert support.max_points == 10
    assert support.parameters["lookback"] == 40


def test_strategy_overrides_indicator_parameters_and_points():
    strategy = load_strategy(
        ROOT / "marketscanner" / "strategies" / "precious_metals_pre_breakout.json"
    )

    indicators = resolve_indicators_for_strategy(strategy)
    support = next(ind for ind in indicators if ind.name == "Rising support line")

    assert support.max_points == 12
    assert support.parameters["lookback"] == 60


def test_selected_indicators_respect_as_of_date():
    dates = pd.date_range("2024-01-01", periods=260, freq="B")
    close = pd.Series(100 + np.arange(len(dates)), index=dates, dtype=float)
    frame = pd.DataFrame(
        {
            "Open": close,
            "High": close + 1,
            "Low": close - 1,
            "Close": close,
            "Volume": 100_000,
        },
        index=dates,
    )

    strategy = load_strategy(
        ROOT / "marketscanner" / "strategies" / "precious_metals_pre_breakout.json"
    )
    indicators = resolve_indicators_for_strategy(strategy)
    result = calculate_selected_indicators(frame, indicators, as_of="2024-09-30")

    assert result.index.max() <= pd.Timestamp("2024-09-30")
    assert len(result) < len(frame)
