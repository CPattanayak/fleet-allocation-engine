"""Deterministic synthetic scenario generator (same seed -> same scenario).

Realism choices:
  * trucks start at 3 depots on the city ring; a mixed fleet (vans, mid trucks,
    reefers, hazmat, liftgate) with different payloads and stop limits
  * orders cluster around a handful of neighbourhoods (Gaussian blobs)
  * ~15% need refrigeration, ~5% hazmat, ~10% liftgate, ~8% fragile handling
  * time windows width depends on `tightness`; ~20% of orders are urgent
"""
from __future__ import annotations

import math
import random
from typing import List, Tuple

from .models import (
    Capability as Cap, City, Depot, GenerateRequest, Location, Order, Tightness, Truck,
)

CITIES = {
    "bengaluru": City(id="bengaluru", name="Bengaluru", center=Location(lat=12.9716, lng=77.5946), radius_km=11),
    "delhi": City(id="delhi", name="New Delhi", center=Location(lat=28.6139, lng=77.2090), radius_km=12),
    "pune": City(id="pune", name="Pune", center=Location(lat=18.5204, lng=73.8567), radius_km=9),
    "hyderabad": City(id="hyderabad", name="Hyderabad", center=Location(lat=17.3850, lng=78.4867), radius_km=11),
}

# (label, capacity kg, capabilities, max stops, speed km/h, cost/km, weight in mix)
TRUCK_TYPES = [
    ("Van", 300, [], 10, 28, 0.8, 4),
    ("Truck", 900, [], 8, 24, 1.2, 3),
    ("Reefer", 600, [Cap.REFRIGERATED, Cap.LIFTGATE], 8, 24, 1.4, 2),
    ("Liftgate", 800, [Cap.LIFTGATE, Cap.FRAGILE], 7, 24, 1.3, 1),
    ("Hazmat", 700, [Cap.HAZMAT], 6, 22, 1.6, 1),
]

WINDOW_WIDTH = {
    Tightness.RELAXED: (180, 420),
    Tightness.NORMAL: (90, 240),
    Tightness.TIGHT: (40, 120),
}

CUSTOMERS = ["Fresh Mart", "City Pharma", "Corner Cafe", "TechHub", "Green Grocer", "Book Nook",
             "Bake House", "Medi Plus", "Home Store", "Spice Co", "Daily Dairy", "Paint Depot",
             "Lab Supplies", "Flower Shop", "Electro World", "Kids Corner"]


def offset(center: Location, dx_km: float, dy_km: float) -> Location:
    lat = center.lat + dy_km / 110.574
    lng = center.lng + dx_km / (111.320 * math.cos(math.radians(center.lat)))
    return Location(lat=round(lat, 6), lng=round(lng, 6))


def polar(center: Location, r_km: float, angle: float) -> Location:
    return offset(center, r_km * math.cos(angle), r_km * math.sin(angle))


def make_depots(city: City, rng: random.Random) -> List[Depot]:
    base = rng.uniform(0, 2 * math.pi)
    names = ["North Hub", "East Hub", "West Hub"]
    return [
        Depot(id=f"D{i + 1}", name=names[i],
              location=polar(city.center, city.radius_km * 0.55, base + i * 2 * math.pi / 3))
        for i in range(3)
    ]


def make_trucks(n: int, depots: List[Depot], rng: random.Random, start_index: int = 1) -> List[Truck]:
    weights = [t[-1] for t in TRUCK_TYPES]
    trucks = []
    for i in range(n):
        label, cap, caps, stops, speed, cpk, _ = rng.choices(TRUCK_TYPES, weights=weights)[0]
        depot = depots[i % len(depots)]
        shift_start = rng.choice([420, 480, 480, 540])
        idx = start_index + i
        trucks.append(Truck(
            id=f"T{idx:03d}", name=f"{label} {idx:02d}",
            depot=offset(depot.location, rng.uniform(-0.3, 0.3), rng.uniform(-0.3, 0.3)),
            capacity_kg=cap, capabilities=list(caps), shift_start=shift_start,
            shift_end=shift_start + rng.choice([600, 660, 720]),
            speed_kmh=speed, max_stops=stops, cost_per_km=cpk,
        ))
    return trucks


def _hotspots(city: City, rng: random.Random, k: int = 6) -> List[Tuple[Location, float]]:
    return [(polar(city.center, city.radius_km * math.sqrt(rng.random()) * 0.85, rng.uniform(0, 2 * math.pi)),
             rng.uniform(1.0, 2.5)) for _ in range(k)]


def make_orders(n: int, city: City, tightness: Tightness, rng: random.Random,
                start_index: int = 1, hotspots=None) -> List[Order]:
    hotspots = hotspots or _hotspots(city, rng)
    lo, hi = WINDOW_WIDTH[tightness]
    orders = []
    for i in range(n):
        if rng.random() < 0.75:
            center, sigma = rng.choice(hotspots)
            loc = offset(center, rng.gauss(0, sigma), rng.gauss(0, sigma))
        else:
            loc = polar(city.center, city.radius_km * math.sqrt(rng.random()), rng.uniform(0, 2 * math.pi))
        caps = []
        r = rng.random()
        if r < 0.15:
            caps.append(Cap.REFRIGERATED)
        elif r < 0.20:
            caps.append(Cap.HAZMAT)
        if rng.random() < 0.10:
            caps.append(Cap.LIFTGATE)
        elif rng.random() < 0.08:
            caps.append(Cap.FRAGILE)
        width = rng.randint(lo, hi)
        start = rng.randrange(510, 1080 - lo, 15)
        idx = start_index + i
        orders.append(Order(
            id=f"O{idx:03d}", customer=f"{rng.choice(CUSTOMERS)} #{rng.randint(1, 99)}", location=loc,
            weight_kg=round(rng.choice([rng.uniform(5, 40), rng.uniform(40, 150)]), 1),
            required_capabilities=caps,
            window_start=start, window_end=min(1140, start + width),
            service_minutes=rng.choice([5, 10, 10, 15, 20]),
            priority=rng.choices([1, 2, 3], weights=[30, 50, 20])[0],
        ))
    return orders


def generate(req: GenerateRequest, seed: int):
    if req.city not in CITIES:
        raise KeyError(req.city)
    city = CITIES[req.city]
    rng = random.Random(seed)
    depots = make_depots(city, rng)
    trucks = make_trucks(req.num_trucks, depots, rng)
    orders = make_orders(req.num_orders, city, req.tightness, rng)
    return city, depots, trucks, orders
