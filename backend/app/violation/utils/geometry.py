from __future__ import annotations

import math
from typing import Iterable


def bbox_bottom_center(bbox: tuple[int, int, int, int]) -> tuple[float, float]:
    x1, y1, x2, y2 = bbox
    return ((x1 + x2) / 2.0, float(y2))


def bbox_width(bbox: tuple[int, int, int, int]) -> float:
    x1, _, x2, _ = bbox
    return float(max(0, x2 - x1))


def point_to_rect_distance(px: float, py: float, rect: tuple[int, int, int, int]) -> float:
    rx, ry, rw, rh = rect
    dx = max(rx - px, 0.0, px - (rx + rw))
    dy = max(ry - py, 0.0, py - (ry + rh))
    return math.hypot(dx, dy)


def min_distance_points_to_rect(points: Iterable[tuple[float, float]], rect: tuple[int, int, int, int]) -> float:
    return min(point_to_rect_distance(px, py, rect) for px, py in points)
