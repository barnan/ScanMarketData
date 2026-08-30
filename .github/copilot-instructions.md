# Copilot Instructions — Bullish Pre-Breakout Market Scanner

## Project overview

This is a Python-based market-data scanning project.

The purpose is to scan a user-selectable universe of stocks, calculate technical indicators from historical OHLCV market data, and rank stocks according to how strongly they exhibit a **bullish pre-breakout technical setup**.

The goal is not simply to find stocks that are already bullish. Prefer stocks that are:
- in an established or improving bullish trend
- consolidating/compressing
- approaching meaningful resistance
- showing improving momentum
- potentially developing a breakout

Avoid over-rewarding stocks that have already broken out or are excessively extended.

## Project architecture

Keep responsibilities separated. The scanner should be modular and configuration-driven.

### `market_scanner.py`

Main application/orchestration layer.

Responsibilities:
- parse command-line arguments
- select the stock universe
- select/load the strategy
- obtain ticker symbols
- download market data
- invoke selected indicators
- calculate scores
- present/save results

Do **not** put indicator-specific mathematical calculations here.

Do not hard-code the S&P 500.

The intended CLI is along the lines of:

```text
python market_scanner.py --universe sp500 --strategy default.json
```

### `stock_universe.py`

Responsible for converting a configured universe into a normalized `list[str]` of tickers.

The scanner should not care how tickers were obtained.

The architecture supports concepts such as:
- explicit ticker lists (`type: "tickers"`)
- index constituents from a source such as Wikipedia (`type: "wikipedia"`)

Keep this extensible for additional universe sources.

Ticker normalization currently includes trimming, upper-casing, duplicate removal, and converting `.` to `-` for Yahoo Finance compatibility.

### `indicator_definition.py`

Defines indicator metadata/configuration.

An indicator definition should identify:
- name
- calculator(s)
- scorer
- maximum points
- indicator-specific parameters

Prefer parameters from strategy configuration rather than hard-coded thresholds.

### `indicator_calculators.py`

Contains technical-indicator calculations from pandas DataFrames.

Examples:
- RSI
- moving averages
- MACD
- ATR
- Bollinger Bands
- volume statistics
- price/range statistics

Keep raw mathematical calculations separate from scoring.

### `scoring.py`

Contains scoring logic.

Scoring functions translate calculated features into points according to the active strategy.

Keep scoring explainable where practical.

### Support-line calculator/scoring

The project includes an intended rising-support-line indicator.

It should calculate:
- support-line slope and intercept
- current support value
- current distance from support
- minimum/average/maximum distance
- number of meaningful touches
- whether all selected closes remain above the line
- whether the line is sufficiently rising
- whether the setup is valid

Mathematical concept:

```text
S(x) = a + b*x
b > 0
Close(x) >= S(x)
```

for all observations in the selected lookback period.

The support definition must be parameterizable, including:
- lookback length
- source column (`Close` or potentially `Low`)
- minimum slope
- touch tolerance
- minimum number of touches
- minimum separation between touches

A touch should use configurable tolerance rather than exact equality.

### Strategy JSON files

Strategy configurations define which indicators are active and how they are weighted/configured.

Keep strategy-specific thresholds and weights in JSON where practical.

Examples may include:
- pre-breakout
- aggressive breakout
- momentum
- volatility squeeze

### Universe JSON files

Universe configurations belong in the `universes` subfolder.

A universe can be an explicit ticker array or a sourced index constituent list.

Example:

```json
{
  "type": "tickers",
  "tickers": ["AAPL", "MSFT", "NVDA"],
  "description": "My watchlist"
}
```

or:

```json
{
  "type": "wikipedia",
  "url": "...",
  "table": 0,
  "ticker_column": "Symbol",
  "description": "S&P 500 constituents"
}
```

### `strategies/`

Strategy JSON files belong here.

### `universes/`

Universe JSON files belong here.

Use centralized constants for default directories/files rather than scattering paths throughout the code.

### `.vscode/launch.json`

Contains VS Code debug configurations. It may pass arguments such as:

```text
--universe sp500
--strategy default.json
```

The CLI should remain the single source of truth so terminal and VS Code execution behave consistently.

## Market data

The scanner works primarily with historical OHLCV:
- Open
- High
- Low
- Close
- Volume

The existing project uses `yfinance` for market-data retrieval.

Use the appropriate OHLCV field for each calculation. For example, closing-price support is different from low-price support.

**Avoid look-ahead bias.** A calculation for a trading day must use only data available on or before that day.

## Pre-breakout indicator philosophy

The objective is:

> Find stocks currently developing a high-quality bullish setup that may precede an upside breakout.

This is different from:

> Find stocks that are already strongly bullish.

A useful pre-breakout setup can combine:

### Trend
- price vs SMA20/SMA50/SMA200
- SMA20 vs SMA50
- SMA50 vs SMA200
- moving-average slopes

Do not excessively reward extreme extension above moving averages.

### Momentum
- RSI(14)
- RSI change/slope
- MACD
- MACD signal
- MACD histogram
- MACD histogram change

Prefer improving momentum over merely high absolute RSI. A healthy rising RSI can be more interesting than RSI > 70.

### Resistance proximity
Calculate:
- 20-day high
- 50-day high
- 100-day high
- percentage distance to resistance

Stocks close to resistance are potentially more interesting for pre-breakout detection.

### Volatility contraction
Consider:
- ATR14
- ATR50
- ATR14 / ATR50
- Bollinger Band width
- relative Bollinger width

Contraction can indicate preparation for expansion, but low volatility alone is not bullish.

### Price compression
Look for narrowing recent price ranges/consolidation, especially below resistance.

### Volume behavior
Consider both:
- volume contraction during consolidation
- volume expansion at/near breakout

### Rising support
A rising support line with multiple meaningful touches can characterize an ascending consolidation.

Evaluate it together with resistance proximity.

### Avoiding late signals
Consider penalties/filters for:
- excessive recent returns
- very high RSI
- large distance above moving averages
- price already substantially above resistance
- unusually large recent breakout moves

The scanner should prefer a setup that is approaching a breakout rather than one that has already made the move.

## Indicator vs strategy

An **indicator** describes the technical state of the stock.

A **strategy** determines how that state contributes to a particular objective.

Do not duplicate calculations merely because different strategies score the same indicator differently.

Prefer:

```text
IndicatorDefinition
    -> calculator
    -> scorer
    -> parameters
```

and let the strategy provide weights/thresholds.

## Backtesting and tuning

Indicator weights and thresholds are hypotheses until validated.

When tuning the scanner:
1. identify historical breakouts
2. inspect features 1, 3, 5 and 10 trading days before breakout
3. compare breakout and non-breakout cases
4. determine which features discriminate
5. tune thresholds/weights
6. validate on out-of-sample periods

Avoid look-ahead bias and, where possible, survivorship bias.

Do not claim predictive value without testing.

## Coding principles

- Inspect the existing repository before changing interfaces.
- Treat actual repository code as authoritative if it differs from these instructions.
- Preserve existing functionality unless the change is intentional.
- Prefer focused, incremental changes.
- Use type hints.
- Use dataclasses where they improve clarity.
- Keep calculations independently testable.
- Keep scoring independently testable.
- Keep network/data retrieval separate from indicator calculations.
- Validate JSON configuration.
- Give useful errors for invalid universe/strategy names.
- Avoid hidden global state.
- Avoid hard-coded S&P-500 assumptions.
- Document non-obvious mathematical logic.
- Prefer descriptive names.
- Add tests for new calculations and scoring.

When adding a new indicator, normally add:
1. calculator
2. scoring function
3. indicator definition
4. strategy JSON configuration
5. tests

## Desired result

The scanner should ultimately produce a ranked, explainable list.

Prefer output that can show both the total score and component contributions, for example:

```text
VZ
Pre-breakout score: 86
Trend: 18/20
Resistance proximity: 19/20
Volatility contraction: 13/15
RSI momentum: 8/10
Rising support: 9/10
```

The exact UI/output can evolve, but explainability is important.

## Copilot behavior

When modifying this project:
- inspect relevant existing files first
- follow the current architecture
- do not invent conflicting interfaces
- make the smallest coherent change
- explain important architectural changes briefly
- keep code testable
- do not silently replace the current strategy
- clearly distinguish existing behavior from proposed improvements
