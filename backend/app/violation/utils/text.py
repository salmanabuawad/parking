import re


def normalize_plate_text(value: str) -> str:
    return re.sub(r'\D', '', str(value))


def normalize_text(value) -> str:
    text = '' if value is None else str(value)
    text = text.strip().lower()
    return re.sub(r'\s+', ' ', text)
