"""Check that our use of SciPy (cost table + 'skip' columns) really gives the best plan.

In single-stop mode Hungarian should match the true optimum, which we find here
by trying every possible plan on small random cases (brute force).
"""
import itertools
import random

import pytest

from app import engine
from app.constraints import TruckState, evaluate, unassigned_cost
from app.models import Algorithm, AllocationRequest, Weights

from .conftest import random_scenario


def brute_force_best(trucks, orders, weights=Weights(), road_factor=1.3):
    """Try every way of giving each order a different truck (or skipping it)."""
    states = [TruckState.initial(t) for t in trucks]
    choices = [None] + list(range(len(trucks)))   # None = skip the order
    best = float("inf")
    for plan in itertools.product(choices, repeat=len(orders)):
        used = [c for c in plan if c is not None]
        if len(used) != len(set(used)):
            continue                                # same truck twice - not allowed
        total = 0.0
        for order, c in zip(orders, plan):
            if c is None:
                total += unassigned_cost(order, weights)
                continue
            ev = evaluate(states[c], order, weights, road_factor)
            if not ev.feasible:
                break
            total += ev.cost
        else:
            best = min(best, total)
    return best


@pytest.mark.parametrize("seed", range(25))
def test_single_stop_hungarian_matches_brute_force(seed):
    rng = random.Random(seed)
    trucks, orders = random_scenario(seed, n_trucks=rng.randint(1, 4), n_orders=rng.randint(1, 5))
    result = engine.run(AllocationRequest(trucks=trucks, orders=orders,
                                          algorithm=Algorithm.HUNGARIAN, single_stop=True))
    assert result.metrics.objective_cost == pytest.approx(brute_force_best(trucks, orders), abs=0.05)


def test_more_orders_than_trucks_some_are_skipped():
    trucks, orders = random_scenario(3, n_trucks=2, n_orders=6)
    r = engine.run(AllocationRequest(trucks=trucks, orders=orders,
                                     algorithm=Algorithm.HUNGARIAN, single_stop=True))
    assert r.metrics.assigned_orders <= 2
    assert r.metrics.assigned_orders + r.metrics.unassigned_orders == 6
