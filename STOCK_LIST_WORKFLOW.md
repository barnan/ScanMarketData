# Stock list / market scanner separation

The scanner no longer knows anything about the S&P 500. It only scans tickers supplied to it.

## 1. Create an S&P 500 list

```bash
python stock_list_creator.py --source sp500 --output stocks/sp500.txt
```

The list creator is the only component that knows how to obtain the S&P 500 constituents.

## 2. Scan that list

```bash
python market_scanner_refactored.py --tickers-file stocks/sp500.txt
```

## 3. Scan any custom list

Create a text file with one Yahoo Finance ticker per line, then pass it to the scanner:

```bash
python market_scanner_refactored.py --tickers-file stocks/custom_example.txt
```

Comments beginning with `#` and empty lines are ignored.

## 4. Create a list from another CSV

```bash
python stock_list_creator.py \
    --source csv \
    --input my_universe.csv \
    --column Symbol \
    --output stocks/my_universe.txt
```

This means you can use virtually any universe provider: another index, ETF holdings, a manually maintained list, a database export, or a screener export.

## Architecture

```text
                 +-------------------------+
                 |   Stock List Creator    |
                 |                         |
                 | S&P500 / CSV / etc.     |
                 +------------+------------+
                              |
                              v
                    stocks/my_list.txt
                              |
                              v
                 +-------------------------+
                 |    Market Scanner       |
                 |                         |
                 | download -> indicators  |
                 | -> score -> results     |
                 +-------------------------+
```

The important boundary is that `scan_tickers()` accepts a list and does not create or discover a universe.
