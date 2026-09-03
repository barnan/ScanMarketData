"""Stock-universe loading and creation.

The scanner should only receive a list of tickers. This module is responsible
for turning a named universe configuration into that list.
"""

from __future__ import annotations

from dataclasses import dataclass
from io import StringIO
from typing import Any

import json
import requests
import pandas as pd


@dataclass(frozen=True)
class UniverseDefinition:
    name: str
    type: str
    description: str = ""
    tickers: tuple[str, ...] = ()
    url: str | None = None
    table: int = 0
    ticker_column: str = "Symbol"


class StockUniverse:
    """Loads stock universes from a JSON configuration file."""

    def __init__(self, definitions: dict[str, UniverseDefinition]):
        self._definitions = definitions

    @classmethod
    def from_json(cls, filename: str) -> "StockUniverse":
        with open(filename, "r", encoding="utf-8") as file:
            config = json.load(file)

        definitions = {}
        for name, raw in config.get("universes", {}).items():
            definitions[name] = UniverseDefinition(
                name=name,
                type=raw["type"],
                description=raw.get("description", ""),
                tickers=tuple(raw.get("tickers", [])),
                url=raw.get("url"),
                table=int(raw.get("table", 0)),
                ticker_column=raw.get("ticker_column", "Symbol"),
            )

        return cls(definitions)

    def names(self) -> list[str]:
        return sorted(self._definitions)

    def get_tickers(self, name: str) -> list[str]:
        if name not in self._definitions:
            available = ", ".join(self.names())
            raise ValueError(
                f"Unknown universe '{name}'. Available universes: {available}"
            )

        definition = self._definitions[name]

        if definition.type == "tickers":
            return self._normalize_tickers(definition.tickers)

        if definition.type == "wikipedia":
            return self._load_wikipedia(definition)

        raise ValueError(
            f"Unsupported universe type '{definition.type}' for '{name}'."
        )

    @staticmethod
    def normalize_tickers(tickers: Any) -> list[str]:
        normalized = []
        seen = set()

        for ticker in tickers:
            ticker = str(ticker).strip().upper().replace(".", "-")
            if ticker and ticker not in seen:
                normalized.append(ticker)
                seen.add(ticker)

        return normalized

    @staticmethod
    def _load_wikipedia(definition: UniverseDefinition) -> list[str]:
        if not definition.url:
            raise ValueError(f"Universe '{definition.name}' has no URL.")

        response = requests.get(
            definition.url,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=30,
        )
        response.raise_for_status()

        tables = pd.read_html(StringIO(response.text))

        try:
            table = tables[definition.table]
        except IndexError as exc:
            raise ValueError(
                f"Wikipedia table {definition.table} does not exist for "
                f"universe '{definition.name}'."
            ) from exc

        if definition.ticker_column not in table.columns:
            raise ValueError(
                f"Ticker column '{definition.ticker_column}' not found in "
                f"universe '{definition.name}'. Available columns: "
                f"{list(table.columns)}"
            )

        return StockUniverse.normalize_tickers(
            table[definition.ticker_column].dropna().tolist()
        )

    def describe(self, name: str) -> str:
        return self._definitions[name].description
