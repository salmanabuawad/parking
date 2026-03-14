"""Vehicle dimensions lookup from CSV/XLSX."""
from __future__ import annotations

from difflib import SequenceMatcher
from pathlib import Path

import pandas as pd

from app.config import settings
from app.violation.schemas import VehicleDimensions, VehicleRegistryRecord
from app.violation.utils.text import normalize_text


def _get_dimensions_path() -> Path:
    path = getattr(settings, 'vehicle_dimensions_path', None)
    if path:
        return Path(path)
    backend_root = Path(__file__).resolve().parent.parent.parent.parent
    return (backend_root / getattr(settings, 'vehicle_dimensions_file', 'data/vehicle_dimensions_sample.csv')).resolve()


def _read_table(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        return None
    ext = path.suffix.lower()
    try:
        if ext == '.csv':
            return pd.read_csv(path, low_memory=False)
        if ext in {'.xlsx', '.xls'}:
            return pd.read_excel(path)
    except Exception:
        return None
    return None


class VehicleDimensionProvider:
    def __init__(self):
        self.df = None
        self.columns = {}
        path = _get_dimensions_path()
        df = _read_table(path)
        if df is not None and not df.empty:
            self.columns = self._detect_columns(df.columns)
            if self.columns:
                df = df.copy()
                df['_manufacturer_key'] = df[self.columns['manufacturer']].map(normalize_text)
                df['_model_key'] = df[self.columns['model']].map(normalize_text)
                df['_year_key'] = pd.to_numeric(df[self.columns.get('year', 'year')], errors='coerce') if self.columns.get('year') else pd.NA
                df['_model_code_key'] = df[self.columns['model_code']].astype(str).str.strip() if self.columns.get('model_code') else ''
                self.df = df

    @staticmethod
    def _first(columns, candidates):
        for c in candidates:
            if c in columns:
                return c
        return None

    def _detect_columns(self, columns) -> dict:
        cols = list(columns)
        return {
            'manufacturer': self._first(cols, ['manufacturer', 'maker', 'brand', 'TOZERET_NM']),
            'model': self._first(cols, ['model_name', 'model', 'KINUY_MISHARI']),
            'year': self._first(cols, ['year', 'production_year', 'SHNAT_YITZUR']),
            'model_code': self._first(cols, ['model_code', 'DEGEM_CD']),
            'length_m': self._first(cols, ['length_m', 'length', 'vehicle_length_m']),
            'width_m': self._first(cols, ['width_m', 'width', 'vehicle_width_m']),
            'height_m': self._first(cols, ['height_m', 'height', 'vehicle_height_m']),
            'wheelbase_m': self._first(cols, ['wheelbase_m', 'wheelbase']),
        }

    def get_dimensions(self, record: VehicleRegistryRecord | None) -> VehicleDimensions | None:
        if record is None or self.df is None or not record.manufacturer or not record.model_name:
            return None
        mk = normalize_text(record.manufacturer)
        mod = normalize_text(record.model_name)
        candidates = self.df[(self.df['_manufacturer_key'] == mk)]
        if candidates.empty:
            return None
        if record.model_code and self.columns.get('model_code'):
            code_match = candidates[candidates['_model_code_key'] == record.model_code]
            if not code_match.empty:
                return self._row_to_dimensions(code_match.iloc[0])
        if record.production_year is not None and self.columns.get('year'):
            exact = candidates[(candidates['_model_key'] == mod) & (candidates['_year_key'] == record.production_year)]
            if not exact.empty:
                return self._row_to_dimensions(exact.iloc[0])
        exact = candidates[candidates['_model_key'] == mod]
        if not exact.empty:
            return self._row_to_dimensions(exact.iloc[0])
        best_score = 0.0
        best_row = None
        for _, row in candidates.iterrows():
            score = SequenceMatcher(None, mod, row['_model_key']).ratio()
            if score > best_score:
                best_score = score
                best_row = row
        if best_row is not None and best_score >= 0.82:
            return self._row_to_dimensions(best_row)
        return None

    def _row_to_dimensions(self, row) -> VehicleDimensions:
        def f(name: str):
            col = self.columns.get(name)
            if not col:
                return None
            val = pd.to_numeric(row.get(col), errors='coerce')
            return float(val) if pd.notna(val) else None
        return VehicleDimensions(
            manufacturer=str(row[self.columns['manufacturer']]),
            model_name=str(row[self.columns['model']]),
            length_m=f('length_m'),
            width_m=f('width_m'),
            height_m=f('height_m'),
            wheelbase_m=f('wheelbase_m'),
        )
