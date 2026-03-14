"""Vehicle registry lookup (optional - graceful when file missing)."""
from __future__ import annotations

from pathlib import Path

from app.config import settings
from app.violation.schemas import VehicleRegistryRecord
from app.violation.utils.text import normalize_plate_text


def _get_registry_path() -> Path:
    path = getattr(settings, 'vehicle_registry_path', None)
    if path and Path(path).exists():
        return Path(path)
    backend_root = Path(__file__).resolve().parent.parent.parent.parent
    return (backend_root / getattr(settings, 'vehicle_registry_file', 'data/registry_sample.csv')).resolve()


class VehicleRegistryService:
    def __init__(self):
        self.df = None
        self.columns = {}
        path = _get_registry_path()
        if path.exists():
            try:
                import pandas as pd
                self.df = pd.read_csv(path, low_memory=False)
                self.columns = self._detect_columns(self.df.columns)
                plate_col = self.columns.get('plate')
                if plate_col:
                    self.df[plate_col] = self.df[plate_col].astype(str).map(normalize_plate_text)
                    self.df = self.df.set_index(plate_col, drop=False)
            except Exception:
                self.df = None

    @staticmethod
    def _first(columns, candidates):
        for c in candidates:
            if c in columns:
                return c
        return None

    def _detect_columns(self, columns) -> dict:
        cols = list(columns)
        return {
            'plate': self._first(cols, ['MISPAR_RECHEV', 'mispar_rechev', 'plate_number', 'plate']),
            'manufacturer': self._first(cols, ['TOZERET_NM', 'tozeret_nm', 'manufacturer']),
            'model': self._first(cols, ['KINUY_MISHARI', 'kinuy_mishari', 'model_name', 'model']),
            'year': self._first(cols, ['SHNAT_YITZUR', 'shnat_yitzur', 'year', 'production_year']),
            'model_code': self._first(cols, ['DEGEM_CD', 'degem_cd', 'model_code']),
            'tyre_spec': self._first(cols, ['TIRE_SIZE', 'tire_size', 'TYRE_SIZE', 'tyre_size', 'MIDA_TZMINA', 'mida_tzmina']),
        }

    def plate_exists(self, plate_number: str) -> bool:
        """True if plate exists in local registry or data.gov.il (Ministry of Transport)."""
        if self.lookup(plate_number) is not None:
            return True
        resource_id = getattr(settings, 'data_gov_il_resource_id', None) or ""
        if resource_id:
            from app.violation.services.data_gov_il import data_gov_il_plate_exists
            result = data_gov_il_plate_exists(normalize_plate_text(plate_number))
            if result is True:
                return True
            if result is False:
                return False
            # None = API unavailable; fail open (allow plate when we can't validate)
        return True

    def lookup(self, plate_number: str) -> VehicleRegistryRecord | None:
        if self.df is None or self.columns.get('plate') is None:
            return None
        plate = normalize_plate_text(plate_number)
        if plate not in self.df.index:
            return None
        row = self.df.loc[plate]
        if hasattr(row, 'iloc'):
            row = row.iloc[0]
        raw = row.to_dict()
        year = None
        if self.columns.get('year'):
            try:
                import pandas as pd
                year_val = pd.to_numeric(raw.get(self.columns['year']), errors='coerce')
                year = int(year_val) if pd.notna(year_val) and year_val is not None else None
            except Exception:
                pass
        return VehicleRegistryRecord(
            plate_number=plate,
            manufacturer=str(raw.get(self.columns.get('manufacturer', ''), '')).strip() or None,
            model_name=str(raw.get(self.columns.get('model', ''), '')).strip() or None,
            production_year=year,
            model_code=str(raw.get(self.columns.get('model_code', ''), '')).strip() or None if self.columns.get('model_code') else None,
            tyre_spec=str(raw.get(self.columns.get('tyre_spec', ''), '')).strip() or None if self.columns.get('tyre_spec') else None,
            raw=raw,
        )
