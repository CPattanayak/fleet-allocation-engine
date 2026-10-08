"""Greedy allocation.

Orders are processed one at a time - most urgent first, then earliest deadline
(EDF) - and each is given to the truck with the lowest marginal cost of
appending it to its current route. Decisions are never revisited.

Ties: trucks whose cost is within TIE_EPS of the best are treated as tied. The
winner among them is the lowest truck ID, so results are always repeatable, and
the explanation says the choice was a tie.
"""
from __future__ import annotations

import time
from typing import List

from ..constraints import TruckState, apply, evaluate
from ..models import AllocationRequest, AllocationResult, Assignment
from .common import build_result, describe_choice, make_assignment

# Costs closer than this are "practically equal". Floating-point maths rarely gives
# exact equality, and explanations round to 1 decimal, so 0.05 matches what users see.
TIE_EPS = 0.05


def order_key(o):
    return (-o.priority, o.window_end, o.window_start, o.id)


def allocate(req: AllocationRequest, states: List[TruckState]) -> AllocationResult:
    t0 = time.perf_counter()
    assignments: List[Assignment] = []
    unassigned: List[str] = []

    for order in sorted(req.orders, key=order_key):
        candidates = []
        for s in states:
            ev = evaluate(s, order, req.weights, req.road_factor)
            if ev.feasible:
                candidates.append((ev.cost, s.truck.id, s, ev))
        if not candidates:
            unassigned.append(order.id)
            continue
        candidates.sort(key=lambda c: (c[0], c[1]))
        _, _, best, ev = candidates[0]
        runner_id = runner_delta = None
        why = f"Greedy pick (lowest marginal cost {ev.cost:.1f} of {len(candidates)} feasible truck(s)). "
        if len(candidates) > 1:
            runner_id, runner_delta = candidates[1][1], candidates[1][0] - ev.cost
            if runner_delta < TIE_EPS:
                tied = [c[1] for c in candidates if c[0] - ev.cost < TIE_EPS]
                why += (f"Tie between {', '.join(tied)} (cost {ev.cost:.1f}); "
                        f"picked {best.truck.id} by truck ID for a repeatable result. ")
            else:
                why += f"Runner-up {runner_id} would cost +{runner_delta:.1f}. "
        else:
            why += "Only feasible truck. "
        why += describe_choice(order, best, ev)  # before apply: describes pre-stop state
        apply(best, order, ev)
        assignments.append(make_assignment(order, best, ev, 1, why, runner_id, runner_delta))

    return build_result(req, states, assignments, unassigned, rounds=1,
                        runtime_ms=(time.perf_counter() - t0) * 1000)
