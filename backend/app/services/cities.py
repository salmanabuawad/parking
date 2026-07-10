"""City data + geometry helpers, sourced from the DB `cities` table.

Replaces the former hardcoded CITIES dict + anchor-based helpers in the simulation router. Admin-added
cities have no anchor points, so demo-camera placement and street lookups derive from each city's
`bounds` ([[west, south], [east, north]] in lng/lat).
"""
import random

from sqlalchemy.orm import Session

from app.models import City


def load_cities(db: Session, include_inactive: bool = False) -> list[City]:
    q = db.query(City)
    if not include_inactive:
        q = q.filter(City.is_active.is_(True))
    return q.order_by(City.sort_order, City.id).all()


def _bbox(c: City) -> tuple[float, float, float, float]:
    """(west, south, east, north). Falls back to a small box around the center if bounds are unset."""
    b = c.bounds
    if isinstance(b, list) and len(b) == 2 and len(b[0]) == 2 and len(b[1]) == 2:
        (w, s), (e, n) = b[0], b[1]
        return float(w), float(s), float(e), float(n)
    return c.center_lng - 0.02, c.center_lat - 0.02, c.center_lng + 0.02, c.center_lat + 0.02


def street_bbox(c: City) -> list[list[float]]:
    """City area as [[w, s], [e, n]] for OSM street lookups / tile warming."""
    w, s, e, n = _bbox(c)
    return [[w, s], [e, n]]


def random_point_in(c: City) -> tuple[float, float]:
    """A random (lat, lng) within the central ~60% of the city bounds (keeps demo pins near the core)."""
    w, s, e, n = _bbox(c)
    lat = random.uniform(s + (n - s) * 0.2, n - (n - s) * 0.2)
    lng = random.uniform(w + (e - w) * 0.2, e - (e - w) * 0.2)
    return round(lat, 6), round(lng, 6)
