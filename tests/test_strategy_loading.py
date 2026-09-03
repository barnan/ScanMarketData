from pathlib import Path

from marketscanner.strategy_loader import (
    load_strategy,
    resolve_indicators_for_strategy,
)


ROOT = Path(__file__).resolve().parent.parent


def test_strategy_file_loads_active_indicator_selection_only():
    strategy = load_strategy(
        ROOT / "marketscanner" / "strategies" / "pre_breakout_with_support.json"
    )

    assert strategy.name == "Pre-breakout with rising support"
    assert "rising_support_line" in strategy.active_indicators
    assert not hasattr(strategy, "indicator_overrides")

    indicators = resolve_indicators_for_strategy(strategy)
    support = next(ind for ind in indicators if ind.name == "Rising support line")

    assert support.max_points == 10
    assert support.parameters == {}
