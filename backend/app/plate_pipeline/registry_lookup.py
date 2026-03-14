"""
Gov.il registry lookup.
Loads registry CSV, normalizes MISPAR_RECHEV to digits only.
A plate is valid only if it exists in the registry.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pandas as pd


def normalize_plate(value: str) -> str:
    """Extract digits only from plate string."""
    return re.sub(r"\D", "", str(value))


class RegistryLookup:
    """
    Lookup plates against Gov.il private/commercial vehicle registry CSV.
    Exposes exists(plate) and get(plate) with manufacturer, model, year when available.
    """

    PLATE_COL_CANDIDATES = ["MISPAR_RECHEV", "mispar_rechev", "plate_number", "plate"]
    MANUFACTURER_COLS = ["TOZERET_NM", "tozeret_nm", "manufacturer"]
    MODEL_COLS = ["KINUY_MISHARI", "kinuy_mishari", "model_name", "model"]
    YEAR_COLS = ["SHNAT_YITZUR", "shnat_yitzur", "year", "production_year"]

    def __init__(self, csv_path: Path | str | None):
        self.df: pd.DataFrame | None = None
        self._plate_col: str | None = None
        self._cols: dict[str, str] = {}
        if csv_path and Path(csv_path).exists():
            self._load(Path(csv_path))

    def _load(self, path: Path) -> None:
        self.df = pd.read_csv(path, low_memory=False)
        self._plate_col = self._first_col(self.df.columns, self.PLATE_COL_CANDIDATES)
        if self._plate_col:
            self.df[self._plate_col] = self.df[self._plate_col].astype(str).map(normalize_plate)
            self.df = self.df.set_index(self._plate_col, drop=False)
        self._cols = {
            "manufacturer": self._first_col(self.df.columns, self.MANUFACTURER_COLS),
            "model": self._first_col(self.df.columns, self.MODEL_COLS),
            "year": self._first_col(self.df.columns, self.YEAR_COLS),
        }

    def _first_col(self, columns: Any, candidates: list[str]) -> str | None:
        for c in candidates:
            if c in columns:
                return c
        return None

    def exists(self, plate: str) -> bool:
        """True if plate exists in registry."""
        if self.df is None or self._plate_col is None:
            return False
        p = normalize_plate(plate)
        return p in self.df.index

    def get(self, plate: str) -> dict | None:
        """
        Return registry row as dict with manufacturer, model, year when available.
        None if not found.
        """
        if self.df is None or self._plate_col is None:
            return None
        p = normalize_plate(plate)
        if p not in self.df.index:
            return None
        row = self.df.loc[p]
        if isinstance(row, pd.DataFrame):
            row = row.iloc[0]
        raw = row.to_dict()
        out: dict[str, Any] = {"plate": p}
        if self._cols.get("manufacturer"):
            out["manufacturer"] = str(raw.get(self._cols["manufacturer"], "")).strip() or None
        if self._cols.get("model"):
            out["model"] = str(raw.get(self._cols["model"], "")).strip() or None
        if self._cols.get("year"):
            try:
                val = pd.to_numeric(raw.get(self._cols["year"]), errors="coerce")
                out["year"] = int(val) if pd.notna(val) and val is not None else None
            except Exception:
                out["year"] = None
        return out
