"""allocation-service: stateless optimisation microservice.

POST /allocate  -> run one strategy
POST /compare   -> run every strategy on the same input
GET  /algorithms, /health
"""
from __future__ import annotations

import logging
from typing import Dict

from fastapi import FastAPI, HTTPException

from . import engine
from .models import Algorithm, AllocationRequest, AllocationResult

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("allocation-service")

app = FastAPI(title="Allocation Service", version="1.0.0",
              description="Greedy and Hungarian (SciPy linear_sum_assignment) truck-to-order allocation.")

ALGORITHM_INFO = {
    Algorithm.GREEDY: {
        "name": "Greedy (priority + earliest-deadline)",
        "summary": "Processes orders one at a time (urgent first, then earliest deadline) and gives "
                   "each to the truck with the lowest marginal cost. O(n*m). Never revisits a decision.",
    },
    Algorithm.HUNGARIAN: {
        "name": "Batched Hungarian (SciPy)",
        "summary": "Each round solves a global min-cost matching of pending orders to trucks, with "
                   "'leave unassigned' dummy columns, optionally limited to a look-ahead horizon of "
                   "near-term work. Repeats until no truck can take more. Optimal per round.",
    },
}


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok", "service": "allocation-service"}


@app.get("/algorithms")
def algorithms():
    return [{"id": a.value, **info} for a, info in ALGORITHM_INFO.items()]


def _run(req: AllocationRequest) -> AllocationResult:
    try:
        result = engine.run(req)
    except engine.ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    m = result.metrics
    log.info("%s: %d/%d orders, %.1f km, %.1f ms", req.algorithm.value,
             m.assigned_orders, m.total_orders, m.total_distance_km, m.runtime_ms)
    return result


@app.post("/allocate", response_model=AllocationResult)
def allocate(req: AllocationRequest) -> AllocationResult:
    return _run(req)


@app.post("/compare", response_model=Dict[str, AllocationResult])
def compare(req: AllocationRequest) -> Dict[str, AllocationResult]:
    return {a.value: _run(req.model_copy(update={"algorithm": a})) for a in Algorithm}
