"""Thread-safe in-memory scenario repository.

Kept behind a small interface so it can be swapped for Postgres/Redis
without touching the API layer.
"""
from __future__ import annotations

import random
import threading
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from . import generator
from .models import (
    CreateScenarioRequest, GenerateRequest, Order, Scenario, ScenarioSummary, Truck, TruckPatch,
)


class NotFound(KeyError):
    pass


class ScenarioStore:
    def __init__(self) -> None:
        self._items: Dict[str, Scenario] = {}
        self._lock = threading.RLock()

    # -- scenarios ---------------------------------------------------------
    def generate(self, req: GenerateRequest) -> Scenario:
        seed = req.seed if req.seed is not None else random.randrange(1, 1_000_000)
        city, depots, trucks, orders = generator.generate(req, seed)
        sc = Scenario(
            id=uuid.uuid4().hex[:8],
            name=req.name or f"{city.name} - {req.num_trucks} trucks / {req.num_orders} orders",
            city=city, seed=seed, tightness=req.tightness,
            created_at=datetime.now(timezone.utc), depots=depots, trucks=trucks, orders=orders,
        )
        with self._lock:
            self._items[sc.id] = sc
        return sc

    def create(self, req: CreateScenarioRequest) -> Scenario:
        """Make a scenario from what the user typed (or imported). Missing ids get filled in."""
        if req.city not in generator.CITIES:
            raise ValueError(f"unknown city '{req.city}'. Options: {sorted(generator.CITIES)}")
        trucks, orders = [], []
        for t in req.trucks:
            t = t.model_copy()
            t.id = t.id or self._next_id("T", [x.id for x in trucks])
            if any(x.id == t.id for x in trucks):
                raise ValueError(f"duplicate truck id {t.id}")
            t.name = t.name or f"Truck {t.id}"
            trucks.append(t)
        for o in req.orders:
            o = o.model_copy()
            o.id = o.id or self._next_id("O", [x.id for x in orders])
            if any(x.id == o.id for x in orders):
                raise ValueError(f"duplicate order id {o.id}")
            o.customer = o.customer or f"Customer {o.id}"
            orders.append(o)
        sc = Scenario(
            id=uuid.uuid4().hex[:8], name=req.name, city=generator.CITIES[req.city],
            created_at=datetime.now(timezone.utc), depots=[], trucks=trucks, orders=orders,
        )
        with self._lock:
            self._items[sc.id] = sc
        return sc

    def list(self) -> List[ScenarioSummary]:
        with self._lock:
            return [ScenarioSummary(id=s.id, name=s.name, city=s.city.id, num_trucks=len(s.trucks),
                                    num_orders=len(s.orders), created_at=s.created_at)
                    for s in sorted(self._items.values(), key=lambda s: s.created_at, reverse=True)]

    def get(self, sid: str) -> Scenario:
        with self._lock:
            if sid not in self._items:
                raise NotFound(sid)
            return self._items[sid]

    def delete(self, sid: str) -> None:
        with self._lock:
            if self._items.pop(sid, None) is None:
                raise NotFound(sid)

    # -- trucks ------------------------------------------------------------
    def add_truck(self, sid: str, truck: Truck) -> Truck:
        with self._lock:
            sc = self.get(sid)
            truck.id = truck.id or self._next_id("T", [t.id for t in sc.trucks])
            if any(t.id == truck.id for t in sc.trucks):
                raise ValueError(f"truck {truck.id} already exists")
            truck.name = truck.name or f"Truck {truck.id}"
            sc.trucks.append(truck)
            return truck

    def patch_truck(self, sid: str, tid: str, patch: TruckPatch) -> Truck:
        with self._lock:
            sc = self.get(sid)
            for i, t in enumerate(sc.trucks):
                if t.id == tid:
                    sc.trucks[i] = t.model_copy(update=patch.model_dump(exclude_none=True))
                    return sc.trucks[i]
            raise NotFound(tid)

    def update_truck(self, sid: str, tid: str, truck: Truck) -> Truck:
        """Replace a truck's details (the id stays the same)."""
        with self._lock:
            sc = self.get(sid)
            for i, t in enumerate(sc.trucks):
                if t.id == tid:
                    truck = truck.model_copy(update={"id": tid, "name": truck.name or t.name})
                    sc.trucks[i] = truck
                    return truck
            raise NotFound(tid)

    def delete_truck(self, sid: str, tid: str) -> None:
        with self._lock:
            sc = self.get(sid)
            before = len(sc.trucks)
            sc.trucks = [t for t in sc.trucks if t.id != tid]
            if len(sc.trucks) == before:
                raise NotFound(tid)

    # -- orders ------------------------------------------------------------
    def add_order(self, sid: str, order: Order) -> Order:
        with self._lock:
            sc = self.get(sid)
            order.id = order.id or self._next_id("O", [o.id for o in sc.orders])
            if any(o.id == order.id for o in sc.orders):
                raise ValueError(f"order {order.id} already exists")
            order.customer = order.customer or f"Customer {order.id}"
            sc.orders.append(order)
            return order

    def add_random_orders(self, sid: str, count: int, seed: Optional[int] = None) -> List[Order]:
        with self._lock:
            sc = self.get(sid)
            rng = random.Random(seed)
            start = self._next_index([o.id for o in sc.orders])
            new = generator.make_orders(count, sc.city, sc.tightness, rng, start_index=start)
            sc.orders.extend(new)
            return new

    def update_order(self, sid: str, oid: str, order: Order) -> Order:
        """Replace an order's details (the id stays the same)."""
        with self._lock:
            sc = self.get(sid)
            for i, o in enumerate(sc.orders):
                if o.id == oid:
                    order = order.model_copy(update={"id": oid, "customer": order.customer or o.customer})
                    sc.orders[i] = order
                    return order
            raise NotFound(oid)

    def delete_order(self, sid: str, oid: str) -> None:
        with self._lock:
            sc = self.get(sid)
            before = len(sc.orders)
            sc.orders = [o for o in sc.orders if o.id != oid]
            if len(sc.orders) == before:
                raise NotFound(oid)

    # -- helpers -------------------------------------------------------------
    @staticmethod
    def _next_index(ids: List[str]) -> int:
        nums = [int(i[1:]) for i in ids if i[1:].isdigit()]
        return (max(nums) + 1) if nums else 1

    def _next_id(self, prefix: str, ids: List[str]) -> str:
        return f"{prefix}{self._next_index(ids):03d}"
