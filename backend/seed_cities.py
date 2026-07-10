"""Seed the six default cities into the `cities` table.

Idempotent: only inserts keys that don't exist yet, so it never overwrites admin edits on re-deploy.
Center/zoom come from the former hardcoded CITIES dict; bounds are computed from that city's anchor
points the same way the old _city_bounds() did.
"""
from app.database import SessionLocal
from app.models import City

# key: (label, center_lat, center_lng, zoom, [anchor (lat, lng), ...])
DEFAULTS = {
    "netanya": ("נתניה", 32.3215, 34.8532, 13, [
        (32.3286, 34.8590), (32.3240, 34.8615), (32.3320, 34.8600), (32.3340, 34.8635),
        (32.3190, 34.8600), (32.3155, 34.8640), (32.3110, 34.8615), (32.3070, 34.8648),
        (32.3040, 34.8605), (32.3270, 34.8648), (32.3210, 34.8662), (32.3140, 34.8632),
    ]),
    "haifa": ("חיפה", 32.7940, 34.9950, 12, [
        (32.7940, 34.9896), (32.8080, 34.9970), (32.8160, 35.0010), (32.7870, 35.0030),
        (32.7830, 35.0130), (32.8010, 34.9950), (32.7780, 35.0080), (32.8050, 35.0060),
        (32.7920, 34.9990), (32.8120, 35.0040), (32.7990, 35.0100), (32.7890, 35.0050),
    ]),
    "tel-aviv": ("תל אביב", 32.0853, 34.7818, 13, [
        (32.0809, 34.7806), (32.0900, 34.7835), (32.0990, 34.7865), (32.0760, 34.7835),
        (32.0850, 34.7895), (32.0950, 34.7925), (32.1080, 34.7985), (32.0720, 34.7815),
        (32.0690, 34.7905), (32.1030, 34.7905), (32.0880, 34.7955), (32.0800, 34.7885),
    ]),
    "jerusalem": ("ירושלים", 31.7780, 35.2100, 12, [
        (31.7683, 35.2137), (31.7850, 35.2100), (31.7900, 35.2010), (31.7760, 35.2240),
        (31.7620, 35.2120), (31.7810, 35.2200), (31.7950, 35.2240), (31.7700, 35.1960),
        (31.7580, 35.2210), (31.7880, 35.1980), (31.7990, 35.2130), (31.7720, 35.2300),
    ]),
    "tiberias": ("טבריה", 32.7900, 35.5290, 14, [
        (32.7922, 35.5285), (32.7965, 35.5268), (32.7885, 35.5293), (32.7850, 35.5255),
        (32.8000, 35.5275), (32.7805, 35.5268), (32.7765, 35.5290), (32.7925, 35.5250),
        (32.7980, 35.5240), (32.7835, 35.5275), (32.7900, 35.5298), (32.7860, 35.5245),
    ]),
    "bukata": ("בוקעאתא", 33.2007, 35.7794, 15, [
        (33.2005, 35.7770), (33.2020, 35.7790), (33.1990, 35.7755), (33.2015, 35.7745),
        (33.1995, 35.7800), (33.2030, 35.7775), (33.1980, 35.7785), (33.2008, 35.7810),
    ]),
}


def _bounds(anchors):
    lats = [a[0] for a in anchors]
    lngs = [a[1] for a in anchors]
    return [[min(lngs) - 0.025, min(lats) - 0.020], [max(lngs) + 0.025, max(lats) + 0.020]]


def main():
    db = SessionLocal()
    try:
        existing = {c.key for c in db.query(City.key).all()}
        added = 0
        for order, (key, (label, lat, lng, zoom, anchors)) in enumerate(DEFAULTS.items()):
            if key in existing:
                continue
            db.add(City(
                key=key, label=label, center_lat=lat, center_lng=lng, zoom=zoom,
                bounds=_bounds(anchors), sort_order=order, is_active=True,
            ))
            added += 1
        db.commit()
        print(f"seed_cities: added {added} cities ({len(existing)} already present)")
    finally:
        db.close()


if __name__ == "__main__":
    main()
