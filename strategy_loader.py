from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from indicator_definition import IndicatorDefinition
from scoring import INDICATORS


@dataclass(frozen=True)
class StrategyDefinition:
    name: str
    description: str = ""
    active_indicators: tuple[str, ...] = ()


def resolve_strategy_path(path: str | Path) -> Path:
    """Resolve a strategy path from either a bare filename or a direct path."""
    candidate = Path(path)

    if candidate.is_absolute():
        if candidate.exists():
            return candidate
        raise FileNotFoundError(f"Strategy file not found: {candidate}")

    search_paths = [
        candidate,
        Path.cwd() / candidate,
        Path(__file__).resolve().parent / candidate,
        Path(__file__).resolve().parent / "strategies" / candidate,
    ]

    for search_path in search_paths:
        if search_path.exists():
            return search_path

    raise FileNotFoundError(
        f"Strategy file not found: {path}. "
        "Expected a direct path or a file under the strategies folder."
    )


def load_strategy(path: str | Path) -> StrategyDefinition:
    """Load a lightweight strategy definition from JSON.

    JSON selects the active indicator set only. The actual indicator
    definitions, defaults, and thresholds live in Python source code.
    """
    resolved = resolve_strategy_path(path)
    with resolved.open("r", encoding="utf-8") as handle:
        config = json.load(handle)

    return StrategyDefinition(
        name=config.get("name", resolved.stem),
        description=config.get("description", ""),
        active_indicators=tuple(config.get("active_indicators", list(INDICATORS))),
    )


def resolve_indicators_for_strategy(
    strategy: StrategyDefinition,
) -> list[IndicatorDefinition]:
    """Build the active indicator list from the canonical Python definitions."""
    selected: list[IndicatorDefinition] = []

    for indicator_key in strategy.active_indicators:
        if indicator_key not in INDICATORS:
            available = ", ".join(sorted(INDICATORS))
            raise ValueError(
                f"Unknown indicator '{indicator_key}' in strategy '{strategy.name}'. "
                f"Available indicators: {available}"
            )

        base = INDICATORS[indicator_key]
        selected.append(
            IndicatorDefinition(
                name=base.name,
                calculator_names=base.calculator_names,
                scorer=base.scorer,
                max_points=base.max_points,
                parameters=dict(base.parameters or {}),
            )
        )

    return selected
