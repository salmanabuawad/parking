import json
import pandas as pd
import re
import urllib.parse

def normalize_plate(value: str) -> str:
    return re.sub(r"\D", "", str(value))


def data_gov_il_plate_exists(plate: str, resource_id: str = "053cea08-09bc-40ec-8f7a-156f0677aff3") -> bool | None:
    """Check data.gov.il MoT dataset via CKAN datastore_search. Returns True/False/None (unavailable)."""
    if not plate or len(plate) < 7:
        return False
    filters = json.dumps({"mispar_rechev": plate})
    url = f"https://data.gov.il/api/3/action/datastore_search?resource_id={resource_id}&filters={urllib.parse.quote(filters)}&limit=1"
    try:
        import requests
        r = requests.get(url, timeout=10)
        if r.status_code != 200:
            return None
        data = r.json()
        if not data.get("success"):
            return None
        records = data.get("result", {}).get("records", [])
        return len(records) > 0
    except Exception:
        return None


class RegistryLookup:
    def __init__(self, csv_path: str, data_gov_il_resource_id: str | None = None):
        self.df = pd.read_csv(csv_path, low_memory=False)
        plate_col = "MISPAR_RECHEV" if "MISPAR_RECHEV" in self.df.columns else "mispar_rechev"
        self.df[plate_col] = self.df[plate_col].astype(str).map(normalize_plate)
        self.df = self.df.set_index(plate_col, drop=False)
        self.data_gov_il_resource_id = data_gov_il_resource_id or "053cea08-09bc-40ec-8f7a-156f0677aff3"

    def exists(self, plate_text: str) -> bool:
        plate = normalize_plate(plate_text)
        if plate in self.df.index:
            return True
        result = data_gov_il_plate_exists(plate, self.data_gov_il_resource_id)
        if result is True:
            return True
        if result is False:
            return False
        return True  # API unavailable: fail open

    def get(self, plate_text: str):
        plate = normalize_plate(plate_text)
        if plate not in self.df.index:
            return None
        row = self.df.loc[plate]
        if hasattr(row, "iloc"):
            row = row.iloc[0]
        return row.to_dict()
