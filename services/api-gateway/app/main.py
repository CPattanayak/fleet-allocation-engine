"""api-gateway: single entry point for the UI.

* proxies scenario CRUD to fleet-service
* orchestrates allocation: loads a scenario from fleet-service and runs it
  through allocation-service (in parallel for /compare)
* aggregates health of downstream services
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional

import httpx
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

FLEET_URL = os.getenv("FLEET_SERVICE_URL", "http://localhost:8001")
ALLOC_URL = os.getenv("ALLOCATION_SERVICE_URL", "http://localhost:8002")
TIMEOUT = float(os.getenv("UPSTREAM_TIMEOUT_SECONDS", "60"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("api-gateway")


def make_clients(transport: Optional[httpx.AsyncBaseTransport] = None):
    kw = {"timeout": TIMEOUT}
    if transport is not None:
        kw["transport"] = transport
    return httpx.AsyncClient(base_url=FLEET_URL, **kw), httpx.AsyncClient(base_url=ALLOC_URL, **kw)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not hasattr(app.state, "fleet"):
        app.state.fleet, app.state.alloc = make_clients()
    yield
    await app.state.fleet.aclose()
    await app.state.alloc.aclose()


app = FastAPI(title="Fleet Allocation API Gateway", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
                   allow_methods=["*"], allow_headers=["*"])


class RunOptions(BaseModel):
    scenario_id: str
    weights: Dict[str, float] = Field(default_factory=dict)
    road_factor: float = 1.3
    single_stop: bool = False
    hungarian_wait_horizon: Optional[float] = 60


class AllocateBody(RunOptions):
    algorithm: str = "greedy"


async def _upstream(client: httpx.AsyncClient, method: str, path: str, **kw) -> httpx.Response:
    try:
        return await client.request(method, path, **kw)
    except httpx.HTTPError as exc:
        log.error("upstream %s%s failed: %s", client.base_url, path, exc)
        raise HTTPException(502, f"upstream service unavailable: {client.base_url}") from exc


def _json_or_raise(resp: httpx.Response) -> Any:
    if resp.status_code >= 400:
        try:
            detail = resp.json().get("detail", resp.text)
        except ValueError:
            detail = resp.text
        raise HTTPException(resp.status_code, detail)
    return resp.json()


async def _load_scenario(request: Request, sid: str) -> Dict[str, Any]:
    return _json_or_raise(await _upstream(request.app.state.fleet, "GET", f"/scenarios/{sid}"))


async def _allocate(request: Request, scenario: Dict[str, Any], opts: RunOptions, algorithm: str):
    payload = {"trucks": scenario["trucks"], "orders": scenario["orders"], "algorithm": algorithm,
               "weights": opts.weights, "road_factor": opts.road_factor, "single_stop": opts.single_stop,
               "hungarian_wait_horizon": opts.hungarian_wait_horizon}
    return _json_or_raise(await _upstream(request.app.state.alloc, "POST", "/allocate", json=payload))


# --------------------------------------------------------------------------- health / meta
@app.get("/api/health")
async def health(request: Request):
    async def check(name, client):
        try:
            r = await client.get("/health", timeout=3)
            return name, "ok" if r.status_code == 200 else f"http {r.status_code}"
        except httpx.HTTPError:
            return name, "down"
    results = dict(await asyncio.gather(check("fleet-service", request.app.state.fleet),
                                        check("allocation-service", request.app.state.alloc)))
    status = "ok" if all(v == "ok" for v in results.values()) else "degraded"
    return {"status": status, "gateway": "ok", "services": results}


@app.get("/api/cities")
async def cities(request: Request):
    return _json_or_raise(await _upstream(request.app.state.fleet, "GET", "/cities"))


@app.get("/api/algorithms")
async def algorithms(request: Request):
    return _json_or_raise(await _upstream(request.app.state.alloc, "GET", "/algorithms"))


# --------------------------------------------------------------------------- allocation
@app.post("/api/allocate")
async def allocate(body: AllocateBody, request: Request):
    scenario = await _load_scenario(request, body.scenario_id)
    result = await _allocate(request, scenario, body, body.algorithm)
    return {"scenario_id": body.scenario_id, "result": result}


LOWER_IS_BETTER = {"total_distance_km", "avg_distance_per_order_km", "total_wait_minutes",
                   "load_balance_stddev", "objective_cost", "runtime_ms", "unassigned_orders"}
HIGHER_IS_BETTER = {"assigned_orders", "fulfillment_rate", "priority_weighted_fulfillment",
                    "urgent_fulfillment", "avg_slack_minutes", "avg_capacity_utilization"}


def summarise(results: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Per-metric winner between the algorithms."""
    names = list(results)
    out = {}
    for metric in sorted(LOWER_IS_BETTER | HIGHER_IS_BETTER):
        vals = {n: results[n]["metrics"][metric] for n in names}
        best = min(vals.values()) if metric in LOWER_IS_BETTER else max(vals.values())
        winners = [n for n, v in vals.items() if abs(v - best) < 1e-9]
        out[metric] = {"values": vals, "winner": winners[0] if len(winners) == 1 else "tie",
                       "lower_is_better": metric in LOWER_IS_BETTER}
    return out


@app.post("/api/compare")
async def compare(body: RunOptions, request: Request):
    scenario = await _load_scenario(request, body.scenario_id)
    t0 = time.perf_counter()
    greedy, hungarian = await asyncio.gather(_allocate(request, scenario, body, "greedy"),
                                             _allocate(request, scenario, body, "hungarian"))
    results = {"greedy": greedy, "hungarian": hungarian}
    return {"scenario_id": body.scenario_id, "results": results, "summary": summarise(results),
            "wall_time_ms": round((time.perf_counter() - t0) * 1000, 2)}


# --------------------------------------------------------------------------- scenario proxy
@app.api_route("/api/scenarios", methods=["GET", "POST"])
@app.api_route("/api/scenarios/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def scenarios_proxy(request: Request, path: str = ""):
    upstream_path = "/scenarios" + (f"/{path}" if path else "")
    body = await request.body()
    resp = await _upstream(request.app.state.fleet, request.method, upstream_path,
                           params=dict(request.query_params), content=body or None,
                           headers={"content-type": request.headers.get("content-type", "application/json")})
    return Response(content=resp.content, status_code=resp.status_code,
                    media_type=resp.headers.get("content-type"))
