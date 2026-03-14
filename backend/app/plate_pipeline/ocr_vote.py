"""OCR vote aggregation across frames."""

from __future__ import annotations

import re
from collections import Counter
from typing import Callable, Optional

from .config import PLATE_MAX_DIGITS, PLATE_MIN_DIGITS
from .registry_lookup import normalize_plate


def is_plausible_plate(digits: str) -> bool:
    d = re.sub(r"\D", "", digits)
    return PLATE_MIN_DIGITS <= len(d) <= PLATE_MAX_DIGITS


class OCRVote:
    """Collect OCR results across frames, vote for best valid candidate."""

    def __init__(self):
        self.counter: Counter[str] = Counter()

    def add(self, text: str) -> None:
        plate = normalize_plate(text)
        if is_plausible_plate(plate):
            self.counter[plate] += 1

    def best_valid(self, registry_exists: Callable[[str], bool]) -> Optional[str]:
        for plate, count in self.counter.most_common():
            if count < 2:
                continue
            if registry_exists(plate):
                return plate
        for plate, _ in self.counter.most_common():
            if registry_exists(plate):
                return plate
        return None

    def best_any(self) -> Optional[str]:
        return self.counter.most_common(1)[0][0] if self.counter else None

    def all_candidates(self) -> list[tuple[str, int]]:
        return self.counter.most_common()
