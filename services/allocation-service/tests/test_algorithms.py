"""Correctness of both strategies plus the comparisons that matter."""
import pytest

from app import engine
from app.constraints import TruckState, evaluate
from app.models import Algorithm, AllocationRequest, Capability, Weights

from .conftest import make_order, make_truck, random_scenario

ALGOS = list(Algorithm)


def run(trucks, orders, algo, **kw):
    return engine.run(AllocationRequest(trucks=trucks, orders=orders, algorithm=algo, **kw))


def assert_valid(result, trucks, orders):
    """Replay every route from scratch and check every hard constraint."""
    by_t = {t.id: t for t in trucks}
    by_o = {o.id: o for o in orders}
    seen = set()
    for route in result.routes:
        truck = by_t[route.truck_id]
        state = TruckState.initial(truck)
        for stop in route.stops:
            order = by_o[stop.order_id]
            e = evaluate(state, order, Weights(), 1.3)
            assert e.feasible, f"{order.id} on {truck.id}: {e.reason}"
            assert stop.arrival == pytest.approx(e.arrival, abs=0.01)
            from app.constraints import apply
            apply(state, order, e)
            assert order.id not in seen
            seen.add(order.id)
        assert route.load_kg <= truck.capacity_kg
    assert seen == {a.order_id for a in result.assignments}
    assert seen | {u.order_id for u in result.unassigned} == set(by_o)
    assert result.metrics.assigned_orders + result.metrics.unassigned_orders == len(orders)


@pytest.mark.parametrize("algo", ALGOS)
@pytest.mark.parametrize("seed", range(8))
def test_all_assignments_satisfy_hard_constraints(algo, seed):
    trucks, orders = random_scenario(seed)
    assert_valid(run(trucks, orders, algo), trucks, orders)


@pytest.mark.parametrize("algo", ALGOS)
def test_empty_inputs(algo):
    r = run([], [make_order("O")], algo)
    assert r.metrics.assigned_orders == 0 and r.unassigned[0].reason == "No trucks available."
    r = run([make_truck("T")], [], algo)
    assert r.metrics.total_orders == 0 and r.metrics.fulfillment_rate == 1.0


@pytest.mark.parametrize("algo", ALGOS)
def test_capability_respected(algo):
    trucks = [make_truck("PLAIN"), make_truck("COLD", 0.05, capabilities=[Capability.REFRIGERATED])]
    orders = [make_order("ICE", 0.001, required_capabilities=[Capability.REFRIGERATED])]
    r = run(trucks, orders, algo)
    assert r.assignments[0].truck_id == "COLD"


@pytest.mark.parametrize("algo", ALGOS)
def test_unassigned_reason_is_explained(algo):
    trucks = [make_truck("T", capacity_kg=10)]
    r = run(trucks, [make_order("HEAVY", weight_kg=500)], algo)
    assert r.unassigned[0].rejections == {"insufficient_capacity": 1}
    assert "payload" in r.unassigned[0].reason


@pytest.mark.parametrize("algo", ALGOS)
def test_every_assignment_has_explanation(algo, scenario):
    r = run(*scenario, algo)
    assert r.assignments and all(len(a.explanation) > 40 for a in r.assignments)


def test_duplicate_ids_rejected():
    with pytest.raises(engine.ValidationError):
        run([make_truck("T"), make_truck("T")], [], Algorithm.GREEDY)


def greedy_trap():
    """Classic case where greedy is myopic.

    Truck A sits right next to order 1 and fairly close to order 2.
    Truck B is close-ish to order 1 but far from order 2.
    Greedy (order 1 first) takes A for order 1, leaving B to drive far to order 2.
    Optimal: B->1, A->2.
    """
    trucks = [make_truck("A", 0, 0), make_truck("B", 0, 0.03)]
    orders = [make_order("O1", 0, 0.005, window_end=1000), make_order("O2", 0, -0.03, window_end=1001)]
    return trucks, orders


def test_hungarian_beats_greedy_on_trap():
    trucks, orders = greedy_trap()
    g = run(trucks, orders, Algorithm.GREEDY, single_stop=True)
    h = run(trucks, orders, Algorithm.HUNGARIAN, single_stop=True)
    assert {a.order_id: a.truck_id for a in g.assignments} == {"O1": "A", "O2": "B"}
    assert {a.order_id: a.truck_id for a in h.assignments} == {"O1": "B", "O2": "A"}
    assert h.metrics.objective_cost < g.metrics.objective_cost
    assert h.metrics.total_distance_km < g.metrics.total_distance_km
    # Hungarian explains that it overrode the locally-cheapest choice
    o1 = next(a for a in h.assignments if a.order_id == "O1")
    assert "Locally cheapest was A" in o1.explanation


@pytest.mark.parametrize("seed", range(15))
def test_hungarian_optimal_in_single_stop_mode(seed):
    """With one stop per truck, Hungarian is exactly optimal: never worse than greedy."""
    trucks, orders = random_scenario(seed, n_trucks=10, n_orders=25)
    g = run(trucks, orders, Algorithm.GREEDY, single_stop=True)
    h = run(trucks, orders, Algorithm.HUNGARIAN, single_stop=True)
    assert h.metrics.objective_cost <= g.metrics.objective_cost + 1e-6
    assert h.metrics.rounds == 1


def test_priority_wins_when_capacity_is_scarce():
    trucks = [make_truck("T", max_stops=1)]
    orders = [make_order("LOW", 0.001, priority=1), make_order("URGENT", 0.05, priority=3)]
    for algo in ALGOS:
        r = run(trucks, orders, algo)
        assert [a.order_id for a in r.assignments] == ["URGENT"], algo


def test_metrics_consistency(scenario):
    for algo in ALGOS:
        m = run(*scenario, algo).metrics
        assert 0 <= m.fulfillment_rate <= 1
        assert m.trucks_used <= 8
        assert m.total_distance_km >= 0
        assert m.runtime_ms >= 0


@pytest.mark.parametrize("horizon", [None, 0, 30, 60, 240])
@pytest.mark.parametrize("seed", range(4))
def test_hungarian_horizon_variants_are_valid(horizon, seed):
    trucks, orders = random_scenario(seed)
    r = run(trucks, orders, Algorithm.HUNGARIAN, hungarian_wait_horizon=horizon)
    assert_valid(r, trucks, orders)
    if horizon is not None:
        for a in r.assignments:
            if "look-ahead" in a.explanation:
                assert a.wait_minutes <= horizon + 1e-6


def test_look_ahead_avoids_committing_trucks_to_far_future_orders():
    """Pure batched matching solves round 1 for 'one stop each' and dispatches the
    distant FAR truck to the 15:00 order, because NEAR is needed for the 08:00 one.
    With the look-ahead, round 1 only matches near-term work; in round 2 NEAR (now
    free) also takes the afternoon drop and FAR stays home."""
    trucks = [make_truck("NEAR", 0, 0, max_stops=2), make_truck("FAR", 0.09, 0, max_stops=1)]
    orders = [
        make_order("LATE", 0, 0.004, window_start=900, window_end=930),
        make_order("MORNING", 0.002, 0, window_start=480, window_end=500),
    ]
    pure = run(trucks, orders, Algorithm.HUNGARIAN, hungarian_wait_horizon=None)
    ahead = run(trucks, orders, Algorithm.HUNGARIAN, hungarian_wait_horizon=60)
    assert {a.order_id: a.truck_id for a in pure.assignments}["LATE"] == "FAR"
    assert {a.order_id: a.truck_id for a in ahead.assignments} == {"MORNING": "NEAR", "LATE": "NEAR"}
    assert ahead.metrics.total_distance_km < pure.metrics.total_distance_km
    assert ahead.metrics.objective_cost < pure.metrics.objective_cost

def test_greedy_tie_is_deterministic_and_explained():
    """Two identical trucks at the same depot cost exactly the same: the lower
    truck ID wins regardless of input order, and the explanation says it was a tie."""
    for trucks in ([make_truck("T005"), make_truck("T002")], [make_truck("T002"), make_truck("T005")]):
        r = run(trucks, [make_order("O1", 0.01)], Algorithm.GREEDY)
        a = r.assignments[0]
        assert a.truck_id == "T002"
        assert a.runner_up_truck_id == "T005"
        assert a.runner_up_cost_delta == 0.0
        assert "Tie between T002, T005" in a.explanation
        assert "picked T002 by truck ID" in a.explanation


def test_greedy_clear_winner_reports_runner_up():
    trucks = [make_truck("NEAR", 0, 0), make_truck("FAR", 0.05, 0)]
    r = run(trucks, [make_order("O1", 0.002)], Algorithm.GREEDY)
    a = r.assignments[0]
    assert a.truck_id == "NEAR"
    assert a.runner_up_cost_delta > 0.05
    assert "Runner-up FAR would cost +" in a.explanation
    assert "Tie" not in a.explanation
