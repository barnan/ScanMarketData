# Precious-Metals Pre-Breakout Strategy Proposal

## Recommendation

Use the three groups differently:

- **Group 1:** market-regime context and mostly filters
- **Group 2:** sector-regime context and moderate scoring
- **Group 3:** primary stock-ranking score

A useful initial weighting is:

```text
Group 1: 15%
Group 2: 25%
Group 3: 60%
```

A favorable market or sector regime should improve confidence, but the individual stock setup should remain decisive.

The current architecture in `strategy_loader.py`, `indicator_definition.py`, and `scoring.py` is designed around one stock DataFrame. Groups 1 and 2 should therefore be calculated as separate dated context data, rather than forcing benchmark series into every stock DataFrame.

---

# Group 1: General Market Sentiment

## 1. S&P 500 trend and regime

**Measures:** Direction and strength of the broad equity market.

**Calculation:**

```text
SMA20, SMA50, SMA200
SMA50_SLOPE = SMA50[t] / SMA50[t-20] - 1
SP500_RETURN_20 = Close[t] / Close[t-20] - 1
```

Useful regime states:

```text
Bullish: Close > SMA200 and SMA50 > SMA200
Neutral: Close > SMA200 but SMA50 <= SMA200
Bearish: Close < SMA200
```

**Bullish behavior:** Price above SMA200, rising SMA50, positive 20-day return, and no severe recent drawdown.

**Suggested parameters:**

- SMA20, SMA50, SMA200
- 20-day return
- 20-day SMA50 slope
- Optional 60-day return

**Scoring:** Prefer a small regime score, such as 0 to 5. Do not score every moving-average relationship separately because they are highly correlated.

**Role:** Context score and possible hard filter.

---

## 2. VIX level and trend

**Measures:** Implied equity-market volatility and risk aversion.

**Calculation:**

```text
VIX_RATIO = VIX[t] / SMA20(VIX)[t]
VIX_CHANGE_10 = VIX[t] / VIX[t-10] - 1
```

**Bullish behavior:** Moderate or falling VIX, especially when it is below its 20-day average.

**Suggested parameters:**

- VIX level
- VIX SMA20
- 5-day and 10-day change
- Avoid treating a very low VIX as automatically bullish

**Scoring:**

```text
VIX below SMA20 and falling: full points
VIX near SMA20: partial points
VIX sharply rising: zero or warning
```

**Role:** Mostly a filter or regime modifier.

For precious metals, VIX is not always negatively correlated with bullishness. A rising VIX can sometimes accompany gold strength, so it should not be an unconditional rejection filter.

---

## 3. Market breadth

**Measures:** Whether broad market participation supports the index move.

A practical calculation uses a defined universe, such as S&P 500 constituents:

```text
Breadth50 =
    number of stocks with Close > SMA50
    / number of stocks with valid data

Breadth200 =
    number of stocks with Close > SMA200
    / number of stocks with valid data
```

Additional useful measures:

```text
AdvanceDeclineRatio =
    advancing stocks / max(declining stocks, 1)

NewHighRatio =
    new 20-day highs / max(new 20-day lows, 1)
```

**Bullish behavior:**

- Breadth50 above approximately 0.55
- Breadth200 above approximately 0.50
- Breadth improving over 5 to 10 days
- Index strength confirmed by participation

**Suggested parameters:**

- 50-day and 200-day breadth
- 5-day breadth change
- Minimum universe coverage, for example 70%

**Scoring:** Score breadth improvement rather than just a single high reading.

**Role:** Context score. It should not be a stock-level filter unless the strategy explicitly requires a risk-on environment.

---

## 4. Interest-rate trend

For precious metals, use both nominal yields and real yields when available.

**Measures:** Opportunity cost of holding non-yielding assets and changes in monetary conditions.

Possible series:

- 10-year Treasury yield
- 2-year Treasury yield
- 10-year real yield, such as TIPS-derived data
- 10-year minus 2-year spread

**Calculation:**

```text
YieldChange_20 = Yield[t] - Yield[t-20]
RealYieldChange_20 = RealYield[t] - RealYield[t-20]
```

**Bullish behavior for gold:**

- Falling real yields
- Stable or falling nominal yields
- No abrupt yield spike

**Bullish behavior for silver/miners:** More nuanced. Falling yields can help, but industrial-growth expectations also matter.

**Scoring:** Use as a small contextual score. A sharp increase in real yields should be a warning, not necessarily an immediate exclusion.

**Role:** Context modifier or filter against extreme adverse conditions.

---

## 5. USD strength

Use DXY or another consistently sourced dollar index.

**Measures:** Dollar strength, which often acts as a headwind for USD-priced commodities.

**Calculation:**

```text
USD_RETURN_20 = DXY[t] / DXY[t-20] - 1
USD_SMA50_SLOPE = SMA50(DXY)[t] / SMA50(DXY)[t-20] - 1
```

**Bullish behavior for precious metals:**

- DXY below SMA50 or SMA200
- DXY falling over 20 days
- No sharp upside reversal

**Scoring:**

```text
DXY return <= -3%: full points
DXY return between -3% and 0%: partial points
DXY return > 2%: zero or warning
```

**Role:** Particularly useful as a Group 2 modifier, not a general equity-market filter.

---

## Best Group 1 set

Start with:

1. S&P 500 trend regime
2. Market breadth
3. VIX trend
4. USD trend
5. Real-yield trend, if reliable data is available

Avoid giving all five equal weight.

---

# Group 2: Precious-Metals Sector Sentiment

## 1. Gold trend

Use spot gold or a liquid proxy such as GLD.

**Calculation:**

```text
Gold above SMA50
Gold above SMA200
Gold_RETURN_20
Gold_SMA50_SLOPE
```

**Bullish behavior:**

- Gold above SMA200
- SMA50 rising
- Positive 20-day return
- Price consolidating near highs rather than becoming extremely extended

**Scoring:** 0 to 6 points. Reward trend and moderate momentum, but penalize excessive extension.

---

## 2. Silver trend

Use spot silver or SLV.

**Calculation:**

```text
Silver_RETURN_20
Silver_RETURN_60
Silver above SMA50
Silver above SMA200
```

**Bullish behavior:** Silver outperforming or confirming gold, with improving medium-term momentum.

**Scoring:** 0 to 5 points. Silver is more volatile, so use percentile or normalized returns rather than rigid thresholds where possible.

---

## 3. Gold/silver ratio

**Measures:** Relative strength of gold versus silver.

```text
GSR = GoldPrice / SilverPrice
GSR_RETURN_20 = GSR[t] / GSR[t-20] - 1
```

**Interpretation:**

- Falling GSR usually means silver is outperforming gold.
- Rising GSR may indicate defensive precious-metals demand favoring gold.
- Neither direction is universally bullish for every precious-metals stock.

**Scoring:**

- For silver strategies: falling GSR receives points.
- For gold strategies: stable or moderately rising GSR may be acceptable.
- For a mixed mining universe: use it as a context feature, not a strong universal score.

**Role:** Sector subtype modifier, not a universal filter.

---

## 4. Precious-metals ETF trend

Track:

- GLD: gold
- SLV: silver
- GDX: gold miners
- GDXJ: junior gold miners
- SIL or SILJ: silver miners

Calculate:

```text
ETF_RETURN_20
ETF_RETURN_60
ETF above SMA50
ETF above SMA200
ETF_SMA50_SLOPE
```

**Bullish behavior:**

- Miners above their SMA50 and SMA200
- GDX/GDXJ outperforming GLD
- SIL/SILJ confirming silver strength
- Positive but not climactic momentum

**Scoring:** This is one of the strongest sector-context groups. Use a composite score rather than scoring every ETF independently.

Example:

```text
Gold trend: 30%
Silver trend: 20%
Major miners: 25%
Junior miners: 15%
Silver miners: 10%
```

---

## 5. Mining relative strength

For an individual mining stock:

```text
RelativeStrength_20 =
    Stock_RETURN_20 - GDX_RETURN_20

RelativeStrength_60 =
    Stock_RETURN_60 - GDX_RETURN_60
```

For sector ETFs:

```text
GDX_RETURN_20 - GLD_RETURN_20
GDXJ_RETURN_20 - GDX_RETURN_20
```

**Bullish behavior:**

- Mining stocks outperform their relevant metal or mining benchmark.
- Relative strength is positive and improving.
- The stock is not already excessively extended.

**Scoring:** This should be a meaningful Group 2 or Group 3 input, depending on implementation.

For a sector-independent Group 3, call the benchmark a configurable `relative_benchmark`; do not hard-code GDX.

---

## 6. Sector breadth

For a configured precious-metals universe:

```text
SectorBreadth50 =
    stocks with Close > SMA50 / stocks with valid data

SectorBreadth200 =
    stocks with Close > SMA200 / stocks with valid data
```

Also useful:

```text
SectorMomentumBreadth =
    stocks with positive 20-day return / valid stocks
```

**Bullish behavior:**

- More than half of the sector above SMA50
- Breadth rising over 5 to 10 days
- Junior miners participating, not only large ETFs

**Scoring:** 0 to 5 points, with more weight on breadth improvement than on the absolute level.

**Role:** Sector confirmation and universe-level filter.

---

## 7. Sector relative strength versus S&P 500

```text
SectorReturn_20 = GDX_RETURN_20
SP500Return_20 = SP500_RETURN_20

SectorRS_20 = SectorReturn_20 - SP500Return_20
```

Use both absolute and relative performance:

```text
SectorStrong =
    SectorReturn_20 > 0
    and SectorRS_20 > 0
```

**Bullish behavior:** Precious metals rise while also outperforming the broad market.

**Scoring:** 0 to 5 points.

**Warning:** Relative strength can improve simply because the broad market is falling. Require positive absolute sector performance too.

---

## Best Group 2 set

Start with:

1. Gold trend
2. Silver trend
3. Mining ETF composite trend
4. Mining relative strength
5. Sector breadth
6. Sector versus S&P 500
7. Gold/silver ratio as a subtype modifier

---

# Group 3: Sector-Independent Stock Setup

These should operate only on the stock’s OHLCV data, with any benchmark supplied generically through configuration.

## 1. Contracting triangle

Replace visual pattern recognition with two bounded trend lines.

For a lookback window, estimate:

```text
UpperLine(t) = a_high + b_high * t
LowerLine(t) = a_low + b_low * t
Width(t) = UpperLine(t) - LowerLine(t)
```

A valid contracting triangle requires:

```text
b_high < 0
b_low > 0
Width_end < Width_start
Close[t] between LowerLine[t] and UpperLine[t]
```

Use constrained envelopes or pivot regression so the lines do not cross through excessive price observations.

**Suggested parameters:**

- Lookback: 40 to 80 trading days
- Minimum 2 meaningful touches on each side
- Minimum width contraction: 20%
- Minimum initial width: 5% of price
- Maximum current width: configurable

**Bullish behavior:** Price is in the lower half of a narrowing range, close to rising support, without a confirmed upside breakout.

**Scoring:** Score only when the geometry is valid and price is near support. Do not reward contraction by itself.

---

## 2. Rising support

The existing `support_line_calculator.py` is already close to this requirement.

Useful fields include:

- support slope
- current distance from support
- touch count
- all closes above support
- support validity

**Bullish behavior:**

```text
SUPPORT_VALID = True
SUPPORT_IS_RISING = True
SUPPORT_DISTANCE_PCT between 0% and 3%
touch_count >= 3
```

**Scoring:**

- Valid rising line: base points
- Three or more touches: additional points
- Price within 1% to 3%: strongest points
- Price below support: zero or warning

Be careful that the current support implementation chooses the line using the full selected historical window. That is acceptable for an as-of scan, but it must be recomputed separately for every historical evaluation date during backtesting.

---

## 3. Horizontal support

A measurable horizontal support can be defined from local lows.

Example:

1. Find local lows using a centered-looking-back-only pivot rule.
2. Cluster lows whose prices are within a tolerance.
3. Require at least two or three touches.
4. Use the cluster median as support.

```text
support_level = median(clustered_pivot_lows)
distance = Close / support_level - 1
```

**Suggested parameters:**

- Lookback: 60 trading days
- Price tolerance: 1.5% to 3%
- Minimum touches: 2 or 3
- Minimum separation: 3 to 5 days
- Reject support clusters that are too old

**Bullish behavior:** Price is within roughly 0% to 3% above support and has not closed decisively below it.

**Scoring:** Reward proximity and successful recent tests. Penalize a close below support.

---

## 4. Price distance to SMA50/SMA200

```text
DistanceToSMA50 = Close / SMA50 - 1
DistanceToSMA200 = Close / SMA200 - 1
```

**Bullish behavior:** Price approaches a rising moving average without breaking it.

Suggested scoring bands:

```text
0% to 2% above rising SMA: strong
2% to 5% above rising SMA: partial
below SMA: zero or warning
far above SMA: penalty for extension
```

Do not score SMA50 and SMA200 as independent full-strength indicators. They overlap with moving-average structure.

---

## 5. Moving-average structure and slope

Calculate:

```text
SMA50_SLOPE = SMA50[t] / SMA50[t-20] - 1
SMA200_SLOPE = SMA200[t] / SMA200[t-40] - 1
MA_GAP = SMA50 / SMA200 - 1
```

**Bullish behavior:**

- SMA50 rising
- SMA200 flat or rising
- SMA50 approaching SMA200 from below, or already modestly above it
- Price not excessively extended above both

**Scoring:** Reward slope and structure, but not a crossover alone.

A crossover should be treated as an event feature:

```text
CrossedRecently =
    SMA50[t] > SMA200[t]
    and SMA50[t-k] <= SMA200[t-k]
```

Use a window such as 1 to 20 days and give it only a small bonus.

---

## 6. Compression and volatility contraction

Use multiple but related measurements carefully:

```text
ATR_RATIO = ATR10 / ATR50
BB_WIDTH_PERCENTILE =
    percentile rank of current BB width over trailing 100 days
```

**Bullish behavior:**

- Volatility is below its recent baseline
- Price remains above or near support
- Compression occurs below resistance

**Scoring:** Moderate points only. Low volatility alone is not bullish.

The existing `volatility_contraction`, `atr_contraction`, and `bollinger_compression` indicators are partially redundant.

---

## 7. Resistance proximity

Use prior resistance, excluding the current bar:

```text
HIGH20_PREVIOUS = rolling_max(High, 20).shift(1)
DistanceToResistance =
    HIGH20_PREVIOUS / Close - 1
```

The existing `indicator_calculators.py` already applies this `shift(1)` correctly.

**Bullish behavior:** Price is within approximately 0% to 5% below resistance, but has not already moved materially above it.

**Scoring:** Strong score near resistance only when compression and support are also present.

This is one of the best pre-breakout indicators, but weak as a standalone trend signal.

---

## 8. Breakout and retest

Define a breakout without future data:

```text
breakout[t] =
    Close[t] > prior_resistance[t]
    and Close[t] > prior_resistance[t] * (1 + breakout_buffer)
```

For example:

```text
breakout_buffer = 0.5% to 1%
```

Then define a retest window:

```text
t + 2 through t + 20
```

A valid retest requires:

```text
Low or Close approaches prior_resistance
Close remains above prior_resistance - tolerance
Close rebounds from the level
```

For live scanning, only evaluate observations available through today. For historical testing, do not label a breakout as successful using future prices at the signal date.

**Bullish behavior:** Previous resistance becomes support, price holds it, and the retest range contracts.

**Scoring:** Strong setup score, but only after confirming the historical breakout occurred before the current retest.

---

## 9. Momentum improvement

Absolute RSI and MACD are less useful than their direction.

Useful features:

```text
RSI_CHANGE_5 = RSI[t] - RSI[t-5]
MACD_HIST_CHANGE_5 = MACD_HIST[t] - MACD_HIST[t-5]
```

**Bullish behavior:**

- RSI approximately 50 to 70
- RSI rising from a pullback
- MACD histogram improving
- Momentum improving without extreme overbought conditions

**Scoring:** Small supporting score. Avoid separately scoring RSI, MACD, and MACD histogram at full weight.

---

## 10. Volume behavior

For pre-breakout setups:

```text
VolumeRatio20 = Volume / SMA20(Volume)
ConsolidationVolumeRatio =
    SMA5(Volume) / SMA50(Volume)
```

**Bullish behavior:**

- Volume contracts during consolidation or retest
- Occasional accumulation days
- No requirement for breakout volume until the actual breakout

**Scoring:** Small supporting score. Volume contraction is not bullish by itself.

---

# Redundant Indicators

Avoid double-counting these groups:

- Price above SMA50, SMA50 slope, and bullish MA structure
- Price above SMA200 and SMA50/SMA200 relationship
- RSI, MACD, MACD histogram, and recent return
- ATR contraction, volatility ratio, and Bollinger width
- Gold trend, GLD trend, and gold ETF moving averages
- GDX trend and mining-sector relative strength
- ETF trend and sector breadth

A practical solution is to create composite features:

```text
trend_score
momentum_score
compression_score
support_score
relative_strength_score
```

Then assign each composite a maximum point value.

---

# Likely False Signals

Be especially cautious with:

- A moving-average crossover without support, resistance, or compression
- Price above SMA200 after a large extended move
- RSI above 70
- Falling volatility without directional structure
- A stock near resistance but with no volume or momentum improvement
- A single support touch
- A support line fitted to only two points
- Positive relative strength caused only by the benchmark falling
- Sector breadth calculated from a survivorship-biased universe
- Gold rising while mining stocks continue underperforming
- A breakout defined using the current day’s high when the signal is evaluated intraday

---

# Filters Versus Scored Indicators

## Prefer hard filters

- Minimum price
- Minimum average dollar volume
- Minimum historical data length
- Missing-data and stale-data checks
- Invalid support geometry
- Price decisively below support
- Price already far above resistance
- Excessive recent return
- Extreme spread or liquidity conditions

## Prefer soft scoring

- Market trend
- VIX
- Breadth
- USD and real yields
- Gold/silver trends
- Mining relative strength
- Compression
- Momentum improvement
- Resistance proximity
- Support quality
- Breakout-retest quality

The market and sector groups should usually reduce or increase conviction rather than eliminate every candidate.

---

# First Practical Strategy

A good initial strategy could be:

## Filters

```text
Close >= 5
Average dollar volume >= 1,000,000
At least 220 trading days
No close more than 8% above previous 20-day resistance
```

## Group 1: 15 points

```text
S&P 500 regime: 5
Market breadth: 4
VIX trend: 2
USD trend: 2
Real-yield trend: 2
```

## Group 2: 25 points

```text
Gold trend: 5
Silver trend: 4
Mining ETF composite: 6
Mining relative strength: 4
Sector breadth: 3
Sector versus S&P 500: 3
Gold/silver ratio: 0 to 2 subtype modifier
```

## Group 3: 60 points

```text
Support quality: 12
Triangle or horizontal compression: 12
Resistance proximity: 10
SMA50/SMA200 structure: 8
Price near rising MA: 6
Breakout-retest: 8
Momentum improvement: 2
Volume behavior: 2
```

For a stock that has already completed a breakout, reduce the compression score and use the breakout-retest score instead. Do not allow the same event to receive full points from both categories.

---

# JSON Configuration Direction

The current JSON format only selects indicator names:

```json
{
  "name": "Pre-breakout with rising support",
  "active_indicators": [
    "trend_sma200",
    "rising_support_line"
  ]
}
```

This is visible in `pre_breakout_with_support.json`. Thresholds currently live in Python definitions, so strategy-specific parameters cannot yet be expressed fully in JSON.

A future configuration could look like this:

```json
{
  "name": "Precious metals pre-breakout",
  "description": "Sector-aware pre-breakout strategy for precious-metals stocks.",
  "filters": {
    "min_price": 5.0,
    "min_avg_dollar_volume": 1000000,
    "max_distance_above_resistance": 0.08
  },
  "context": {
    "general_market": {
      "enabled": true,
      "weight": 15,
      "indicators": [
        {
          "name": "sp500_regime",
          "max_points": 5,
          "parameters": {
            "fast_window": 50,
            "slow_window": 200,
            "slope_window": 20
          }
        },
        {
          "name": "market_breadth",
          "max_points": 4,
          "parameters": {
            "breadth_window": 50,
            "improvement_window": 5
          }
        },
        {
          "name": "vix_trend",
          "max_points": 2,
          "parameters": {
            "trend_window": 20
          }
        }
      ]
    },
    "sector": {
      "enabled": true,
      "weight": 25,
      "benchmark": "GDX",
      "indicators": [
        {
          "name": "gold_trend",
          "max_points": 5
        },
        {
          "name": "mining_relative_strength",
          "max_points": 4,
          "parameters": {
            "benchmark": "GDX",
            "return_window": 20
          }
        },
        {
          "name": "sector_breadth",
          "max_points": 3
        }
      ]
    }
  },
  "stock_indicators": [
    {
      "name": "rising_support_line",
      "max_points": 12,
      "parameters": {
        "lookback": 40,
        "source_column": "Close",
        "min_slope_pct_per_day": 0.0001,
        "touch_tolerance_pct": 0.01,
        "min_touches": 3,
        "min_touch_separation": 3
      }
    },
    {
      "name": "triangle_compression",
      "max_points": 12,
      "parameters": {
        "lookback": 60,
        "min_width_contraction": 0.2,
        "min_touches_per_side": 2
      }
    },
    {
      "name": "resistance_proximity",
      "max_points": 10,
      "parameters": {
        "lookback": 20,
        "maximum_distance": 0.05
      }
    }
  ]
}
```

The important architectural addition is a separate context contract, conceptually:

```python
MarketContext
SectorContext
```

Each should be calculated for a specific `as_of` date and supplied to the scoring stage. Group 3 indicator definitions can remain compatible with the current `IndicatorDefinition` and stock DataFrame flow.

Before implementing all of this, validate the strategy with historical examples at 1, 3, 5, and 10 trading days before breakouts. The first implementation should probably add only:

1. Market/sector context data structures
2. S&P 500, VIX, gold, GDX, and breadth context indicators
3. A parameterized horizontal-support calculator
4. A parameterized triangle-compression calculator
5. Breakout-retest detection
6. JSON parameter overrides

No code changes were made in preparing this proposal.
