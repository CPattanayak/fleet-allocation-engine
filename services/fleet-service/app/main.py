"""fleet-service: owns scenario data (trucks, orders, depots)."""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query, Response

from .generator import CITIES
from .models import (
    City, CreateScenarioRequest, GenerateRequest, Order, Scenario, ScenarioSummary, Truck, TruckPatch,
)
from .store import NotFound, ScenarioStore

store = ScenarioStore()


def seed_demo_scenarios(target: ScenarioStore) -> None:
    """Optional demo data (off by default; set SEED_DEFAULT_SCENARIO=true to enable)."""
    target.generate(GenerateRequest(name="Demo - Bengaluru quiet day (12 trucks / 60 orders)", seed=42))
    target.generate(GenerateRequest(name="Demo - Bengaluru peak day (25 trucks / 150 orders)",
                                    num_trucks=25, num_orders=150, seed=42))


@asynccontextmanager
async def lifespan(_: FastAPI):
    # By default the app starts empty and scenarios are created from the UI.
    if os.getenv("SEED_DEFAULT_SCENARIO", "false").lower() == "true" and not store.list():
        seed_demo_scenarios(store)
    yield


app = FastAPI(title="Fleet Service", version="1.0.0", lifespan=lifespan,
              description="Scenario, truck and order management.")


def _get(sid: str) -> Scenario:
    try:
        return store.get(sid)
    except NotFound:
        raise HTTPException(404, f"scenario {sid} not found")


@app.get("/health")
def health():
    return {"status": "ok", "service": "fleet-service"}


@app.get("/cities", response_model=List[City])
def cities():
    return list(CITIES.values())


@app.post("/scenarios", response_model=Scenario, status_code=201)
def create_scenario(req: CreateScenarioRequest):
    """Create an empty scenario, or one with trucks/orders supplied by the user (JSON import)."""
    try:
        return store.create(req)
    except ValueError as exc:
        raise HTTPException(422, str(exc))


@app.post("/scenarios/generate", response_model=Scenario, status_code=201)
def generate(req: GenerateRequest):
    if req.city not in CITIES:
        raise HTTPException(422, f"unknown city '{req.city}'. Options: {sorted(CITIES)}")
    return store.generate(req)


@app.get("/scenarios", response_model=List[ScenarioSummary])
def list_scenarios():
    return store.list()


@app.get("/scenarios/{sid}", response_model=Scenario)
def get_scenario(sid: str):
    return _get(sid)


@app.delete("/scenarios/{sid}", status_code=204)
def delete_scenario(sid: str):
    try:
        store.delete(sid)
    except NotFound:
        raise HTTPException(404, f"scenario {sid} not found")
    return Response(status_code=204)


def _call(fn, *args):
    try:
        return fn(*args)
    except NotFound as exc:
        raise HTTPException(404, f"{exc.args[0]} not found")
    except ValueError as exc:
        raise HTTPException(409, str(exc))


@app.post("/scenarios/{sid}/trucks", response_model=Truck, status_code=201)
def add_truck(sid: str, truck: Truck):
    return _call(store.add_truck, sid, truck)


@app.patch("/scenarios/{sid}/trucks/{tid}", response_model=Truck)
def patch_truck(sid: str, tid: str, patch: TruckPatch):
    return _call(store.patch_truck, sid, tid, patch)


@app.put("/scenarios/{sid}/trucks/{tid}", response_model=Truck)
def update_truck(sid: str, tid: str, truck: Truck):
    return _call(store.update_truck, sid, tid, truck)


@app.delete("/scenarios/{sid}/trucks/{tid}", status_code=204)
def delete_truck(sid: str, tid: str):
    _call(store.delete_truck, sid, tid)
    return Response(status_code=204)


@app.post("/scenarios/{sid}/orders", response_model=Order, status_code=201)
def add_order(sid: str, order: Order):
    return _call(store.add_order, sid, order)


@app.post("/scenarios/{sid}/orders/random", response_model=List[Order], status_code=201)
def add_random_orders(sid: str, count: int = Query(5, ge=1, le=200), seed: Optional[int] = None):
    return _call(store.add_random_orders, sid, count, seed)


@app.put("/scenarios/{sid}/orders/{oid}", response_model=Order)
def update_order(sid: str, oid: str, order: Order):
    return _call(store.update_order, sid, oid, order)


@app.delete("/scenarios/{sid}/orders/{oid}", status_code=204)
def delete_order(sid: str, oid: str):
    _call(store.delete_order, sid, oid)
    return Response(status_code=204)
