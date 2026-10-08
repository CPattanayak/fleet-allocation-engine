"""Entry point used by the API: validates input and dispatches to a strategy."""
from __future__ import annotations

from typing import Callable, Dict

from .algorithms import greedy, hungarian
from .constraints import TruckState
from .models import Algorithm, AllocationRequest, AllocationResult

STRATEGIES: Dict[Algorithm, Callable] = {
    Algorithm.GREEDY: greedy.allocate,
    Algorithm.HUNGARIAN: hungarian.allocate,
}


class ValidationError(ValueError):
    pass


def run(req: AllocationRequest) -> AllocationResult:
    _validate(req)
    trucks = req.trucks
    if req.single_stop:
        # Pure one-shot matching: one stop per truck and no look-ahead gating, so the
        # Hungarian result is the exact optimum of the objective.
        trucks = [t.model_copy(update={"max_stops": 1}) for t in trucks]
        req = req.model_copy(update={"hungarian_wait_horizon": None})
    states = [TruckState.initial(t) for t in trucks]
    return STRATEGIES[req.algorithm](req, states)


def _validate(req: AllocationRequest) -> None:
    for label, items in (("truck", req.trucks), ("order", req.orders)):
        ids = [i.id for i in items]
        dupes = {i for i in ids if ids.count(i) > 1}
        if dupes:
            raise ValidationError(f"duplicate {label} ids: {sorted(dupes)}")
