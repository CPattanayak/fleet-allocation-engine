import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models import Capability, Location, Order, Truck  # noqa: E402

BASE = (12.9716, 77.5946)  # Bengaluru


def loc(dlat=0.0, dlng=0.0):
    return Location(lat=BASE[0] + dlat, lng=BASE[1] + dlng)


def make_truck(id, dlat=0.0, dlng=0.0, **kw):
    kw.setdefault("capacity_kg", 1000)
    return Truck(id=id, depot=loc(dlat, dlng), **kw)


def make_order(id, dlat=0.0, dlng=0.0, **kw):
    kw.setdefault("weight_kg", 50)
    kw.setdefault("window_start", 480)
    kw.setdefault("window_end", 1100)
    return Order(id=id, location=loc(dlat, dlng), **kw)


def random_scenario(seed, n_trucks=8, n_orders=40, spread=0.12):
    rng = random.Random(seed)
    caps = list(Capability)
    trucks = [
        make_truck(f"T{i}", rng.uniform(-spread, spread) / 2, rng.uniform(-spread, spread) / 2,
                   capacity_kg=rng.choice([300, 500, 800]),
                   capabilities=rng.sample(caps, rng.choice([0, 0, 1, 2])),
                   max_stops=rng.randint(3, 8))
        for i in range(n_trucks)
    ]
    orders = []
    for i in range(n_orders):
        start = rng.randint(480, 1000)
        orders.append(make_order(
            f"O{i}", rng.uniform(-spread, spread), rng.uniform(-spread, spread),
            weight_kg=rng.randint(10, 200),
            required_capabilities=rng.sample(caps, 1) if rng.random() < 0.2 else [],
            window_start=start, window_end=min(1200, start + rng.randint(30, 240)),
            priority=rng.randint(1, 3)))
    return trucks, orders


@pytest.fixture
def scenario():
    return random_scenario(7)
