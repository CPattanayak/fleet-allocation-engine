"""Distance helpers. No routing API is used: road distance is approximated as
great-circle distance multiplied by a configurable road factor (~1.3 in cities)."""
from __future__ import annotations

import math

from .models import Location

EARTH_RADIUS_KM = 6371.0088


def haversine_km(a: Location, b: Location) -> float:
    lat1, lng1, lat2, lng2 = map(math.radians, (a.lat, a.lng, b.lat, b.lng))
    dlat, dlng = lat2 - lat1, lng2 - lng1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(min(1.0, math.sqrt(h)))


def road_km(a: Location, b: Location, road_factor: float) -> float:
    return haversine_km(a, b) * road_factor


def travel_minutes(km: float, speed_kmh: float) -> float:
    return km / speed_kmh * 60.0


def fmt_time(minutes: float) -> str:
    m = int(round(minutes))
    return f"{m // 60:02d}:{m % 60:02d}"
