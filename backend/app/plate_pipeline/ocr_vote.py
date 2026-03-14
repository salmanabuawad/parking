"""
OCR vote aggregation across frames.
Accept only plausible 7/8-digit candidates; prefer most frequent high-confidence one.
"""
from __future__ import annotations

import re
from collections import Counter
from typing import Callable, Optional

from .config import PLATE_MAX_DIGITS, PLATE_MIN_DIGITS
from .registry_lookup import normalize_plate


def is_plausible_plate(digits: str) -> bool:
    """Israeli plates: 7 or 8 digits only."""
    d = re.sub(r"\D", "", digits)
    return PLATE_MIN_DIGITS <= len(d) <= PLATE_MAX_DIGITS


class OCRVote:
    """
    Collect OCR results across frames, vote for best valid candidate.
    best_valid(registry) returns plate only if it exists in registry.
    """

    def __init__(self):
        self.counter: Counter[str] = Counter()

    def add(self, text: str) -> None:
        plate = normalize_plate(text)
        if is_plausible_plate(plate):
            self.counter[plate] += 1

    def best_valid(
        self,
        registry_exists: Callable[[str], bool],
    ) -> Optional[str]:
        """Return most frequent candidate that exists in registry, or None."""
        for plate, _ in self.counter.most_common():
            if registry_exists(plate):
                return plate
        return None

    def all_candidates(self) -> list[tuple[str, int]]:
        """Return all candidates sorted by count descending."""
        return self.counter.most_common()
