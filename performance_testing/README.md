# Performance Testing

This package evaluates CSV output produced by `marketscanner`.

## Workflow

1. Run the scanner for a historical date:

   ```powershell
   python -m marketscanner.market_scanner --universe sp500 --strategy pre_breakout_with_support.json --as-of 2024-01-10
   ```

2. Evaluate the resulting picks after a forward trading-day interval:

   ```powershell
   python -m performance_testing.performance_tester --as-of 2024-01-10 --forward-days 20
   ```

The evaluator reads `results/top_candidates.csv` by default, falling back to
`results/bullish_setup.csv`. Use `--results-file` to select a specific scanner
output and `--output` to select the detailed evaluation CSV.

The reported percentage is the share of evaluated tickers whose adjusted close
is higher after the requested number of trading sessions. Tickers without
sufficient price data are reported but excluded from that percentage.
