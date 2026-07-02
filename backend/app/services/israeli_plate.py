"""Israeli plate validation/normalization (7 or 8 digits). From snippets."""


def normalize_israeli_plate(value: str | None) -> str | None:
    if not value:
        return None
    digits = "".join(ch for ch in value if ch.isdigit())
    if len(digits) not in (7, 8):
        return None
    return digits


def format_israeli_plate(digits: str | None) -> str | None:
    if not digits:
        return None
    digits = "".join(ch for ch in digits if ch.isdigit())
    if len(digits) == 7:
        return f"{digits[:2]}-{digits[2:5]}-{digits[5:]}"
    if len(digits) == 8:
        return f"{digits[:3]}-{digits[3:5]}-{digits[5:]}"
    return digits
