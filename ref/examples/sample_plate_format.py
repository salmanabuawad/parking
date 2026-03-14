def classify_plate_format(box_w: int, box_h: int):
    if box_h <= 0:
        return None

    ratio = box_w / box_h

    presets = [
        {"name": "private_long", "ratio": 52 / 12, "width_cm": 52.0, "height_cm": 12.0},
        {"name": "private_rect", "ratio": 32 / 16, "width_cm": 32.0, "height_cm": 16.0},
        {"name": "motorcycle", "ratio": 17 / 16, "width_cm": 17.0, "height_cm": 16.0},
        {"name": "scooter", "ratio": 17 / 12, "width_cm": 17.0, "height_cm": 12.0},
    ]

    return min(presets, key=lambda p: abs(p["ratio"] - ratio))
