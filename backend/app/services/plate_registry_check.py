"""Multi-stage registry deep-check (requirement: cross-check reads against the gov vehicle list).

The Israeli plate space is DENSE — most 7-8 digit numbers belong to *some* real vehicle — so a
registered near-variant is NOT proof of the true plate (a misread can coincidentally match another
car). We therefore split by evidence strength:

Stage 1  read is in the registry            -> confirmed  (store the vehicle for inspector cross-check)
Stage 2  another OCR candidate (a plate the  -> corrected  (SAFE: image-grounded — the OCR actually read
         engine actually read in some frame)              it in a frame AND the registry agrees)
         is registered
Stage 3  synthetic OCR-confusion near-variant -> not_in_registry + `suggestions`  (hints only, NEVER
         is registered                                    auto-applied — dense registry makes this unsafe)
else                                          -> not_in_registry (no suggestions)

Registry off/unreachable -> registry_unavailable (don't invent anything from failed lookups).

Returns {plate, status, corrected, vehicle, suggestions}. `plate` is the corrected plate only when
status == corrected; otherwise it's the original read. `suggestions` is a list of
{plate, make} the inspector can consider when the read isn't registered.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.services.israeli_plate import normalize_israeli_plate
from app.services.vehicle_registry_api import lookup_vehicle_by_plate

# Common OCR digit confusions (glyph/blur similarity), ordered by likelihood.
_CONFUSIONS = {
    "0": ["8", "6", "9"],
    "1": ["7", "4"],
    "2": ["7", "1"],
    "3": ["8", "9", "5"],
    "4": ["9", "1"],
    "5": ["6", "8", "3"],
    "6": ["8", "5", "0"],
    "7": ["1", "2"],
    "8": ["0", "6", "3", "9"],
    "9": ["4", "3", "8", "0"],
}

_MAX_SUGGESTIONS = 5


def _make(record: dict | None) -> str:
    if not record:
        return ""
    return record.get("tozeret_nm") or record.get("kinuy_mishari") or ""


def deep_check(db: Session, read: str, candidates: list[str] | None = None) -> dict:
    read = normalize_israeli_plate(read)
    base = {"plate": read or "", "status": "invalid", "corrected": False, "vehicle": None, "suggestions": []}
    if not read:
        return base

    _cache: dict[str, dict] = {}

    def lookup(p: str) -> dict:
        if p not in _cache:
            _cache[p] = lookup_vehicle_by_plate(db, p)
        return _cache[p]

    # Stage 1 — the read itself
    first = lookup(read)
    st = first.get("status")
    if st == "plate_found":
        return {"plate": read, "status": "confirmed", "corrected": False,
                "vehicle": first.get("record"), "suggestions": []}
    if st in ("disabled", "lookup_failed"):
        return {"plate": read, "status": "registry_unavailable", "corrected": False,
                "vehicle": None, "suggestions": []}

    tried = {read}

    # Stage 2 — other OCR candidates the engine actually read (image-grounded) → SAFE auto-correct
    for c in (candidates or []):
        c = normalize_israeli_plate(c)
        if not c or c in tried:
            continue
        tried.add(c)
        r = lookup(c)
        if r.get("status") == "plate_found":
            return {"plate": c, "status": "corrected", "corrected": True,
                    "vehicle": r.get("record"), "suggestions": []}

    # Stage 3 — synthetic near-variants → SUGGESTIONS only (never auto-applied)
    suggestions: list[dict] = []
    for i, ch in enumerate(read):
        for alt in _CONFUSIONS.get(ch, []):
            v = read[:i] + alt + read[i + 1:]
            if v in tried:
                continue
            tried.add(v)
            r = lookup(v)
            if r.get("status") == "plate_found":
                suggestions.append({"plate": v, "make": _make(r.get("record"))})
                if len(suggestions) >= _MAX_SUGGESTIONS:
                    break
        if len(suggestions) >= _MAX_SUGGESTIONS:
            break

    return {"plate": read, "status": "not_in_registry", "corrected": False,
            "vehicle": None, "suggestions": suggestions}
