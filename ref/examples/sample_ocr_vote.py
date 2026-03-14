from collections import Counter
import re

def normalize_plate(value: str) -> str:
    return re.sub(r"\D", "", str(value))

class OCRVote:
    def __init__(self):
        self.counter = Counter()

    def add(self, text: str):
        plate = normalize_plate(text)
        if len(plate) in (7, 8):
            self.counter[plate] += 1

    def best_valid(self, registry_lookup):
        for plate, _count in self.counter.most_common():
            if registry_lookup.exists(plate):
                return plate
        return None
