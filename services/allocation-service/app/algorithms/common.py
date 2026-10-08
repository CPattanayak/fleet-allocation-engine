"""Shared helpers: explanations, unassigned diagnostics, result assembly & metrics."""
from __future__ import annotations

import statistics
from collections import Counter
from typing import Dict, List, Optional

from ..constraints import (
    CAPABILITY, CAPACITY, MAX_STOPS, SHIFT, TIME_WINDOW, UNAVAILABLE,
    Evaluation, TruckState, evaluate, unassigned_cost,
)
from ..geo import fmt_time, road_km
from ..models import (
    AllocationRequest, AllocationResult, Assignment, Metrics, Order, TruckRoute, UnassignedOrder,
)

REASON_TEXT = {
    UNAVAILABLE: "truck(s) off duty",
    CAPABILITY: "truck(s) lack a required capability",
    CAPACITY: "truck(s) without enough remaining payload",
    MAX_STOPS: "truck(s) with a full route",
    TIME_WINDOW: "truck(s) would arrive after the window closes",
    SHIFT: "truck(s) could not get back to depot before shift end",
}


def describe_choice(order: Order, state: TruckState, ev: Evaluation) -> str:
    t = state.truck
    parts = [
        f"{t.id} drives {ev.distance_km:.1f} km and arrives {fmt_time(ev.arrival)} "
        f"(window {fmt_time(order.window_start)}-{fmt_time(order.window_end)}, "
        f"{ev.slack_minutes:.0f} min slack)",
        f"payload {state.load_kg:.0f}+{order.weight_kg:.0f}/{t.capacity_kg:.0f} kg",
    ]
    if ev.wait_minutes >= 1:
        parts.append(f"waits {ev.wait_minutes:.0f} min for the window")
    if order.required_capabilities:
        parts.append("has " + ", ".join(c.value for c in order.required_capabilities))
    if ev.over_qualification:
        parts.append(f"{ev.over_qualification} special capability(ies) unused")
    return "; ".join(parts) + "."


def diagnose_unassigned(
    order: Order, states: List[TruckState], req: AllocationRequest
) -> UnassignedOrder:
    counts: Counter = Counter()
    for s in states:
        ev = evaluate(s, order, req.weights, req.road_factor)
        counts[ev.reason or "feasible"] += 1
    feasible = counts.pop("feasible", 0)
    if feasible:
        reason = (
            f"{feasible} truck(s) could still serve it, but the solver preferred to leave it "
            f"(serving cost exceeded the priority-{order.priority} unassigned penalty)."
        )
    elif counts:
        top = ", ".join(f"{n} {REASON_TEXT.get(code, code)}" for code, n in counts.most_common())
        reason = f"No feasible truck: {top}."
    else:
        reason = "No trucks available."
    return UnassignedOrder(order_id=order.id, reason=reason, rejections=dict(counts))


def build_result(
    req: AllocationRequest,
    states: List[TruckState],
    assignments: List[Assignment],
    unassigned_ids: List[str],
    rounds: int,
    runtime_ms: float,
) -> AllocationResult:
    orders_by_id: Dict[str, Order] = {o.id: o for o in req.orders}
    unassigned = [diagnose_unassigned(orders_by_id[oid], states, req) for oid in unassigned_ids]

    routes: List[TruckRoute] = []
    total_km = 0.0
    for s in states:
        if not s.stops:
            continue
        back = road_km(s.position, s.truck.depot, req.road_factor)
        routes.append(TruckRoute(
            truck_id=s.truck.id, stops=s.stops,
            total_distance_km=round(s.distance_km + back, 3),
            return_distance_km=round(back, 3),
            load_kg=round(s.load_kg, 2), capacity_kg=s.truck.capacity_kg,
            end_time=round(s.time + back / s.truck.speed_kmh * 60, 2),
        ))
        total_km += s.distance_km + back

    metrics = compute_metrics(req, states, assignments, unassigned_ids, total_km, rounds, runtime_ms)
    return AllocationResult(
        algorithm=req.algorithm,
        assignments=sorted(assignments, key=lambda a: (a.truck_id, a.sequence)),
        unassigned=unassigned, routes=routes, metrics=metrics,
    )


def compute_metrics(
    req: AllocationRequest, states: List[TruckState], assignments: List[Assignment],
    unassigned_ids: List[str], total_km: float, rounds: int, runtime_ms: float,
) -> Metrics:
    orders = req.orders
    n = len(orders)
    assigned_ids = {a.order_id for a in assignments}
    prio_total = sum(o.priority for o in orders) or 1
    prio_served = sum(o.priority for o in orders if o.id in assigned_ids)
    urgent = [o for o in orders if o.priority == 3]
    urgent_served = sum(1 for o in urgent if o.id in assigned_ids)

    available = [s for s in states if s.truck.available]
    used = [s for s in available if s.stops]
    slacks = list(_slacks(req, states))
    stop_counts = [len(s.stops) for s in available]

    by_id = {o.id: o for o in orders}
    objective = sum(a.cost for a in assignments) + sum(
        unassigned_cost(by_id[oid], req.weights) for oid in unassigned_ids
    )
    return Metrics(
        total_orders=n,
        assigned_orders=len(assignments),
        unassigned_orders=len(unassigned_ids),
        fulfillment_rate=round(len(assignments) / n, 4) if n else 1.0,
        priority_weighted_fulfillment=round(prio_served / prio_total, 4),
        urgent_fulfillment=round(urgent_served / len(urgent), 4) if urgent else 1.0,
        total_distance_km=round(total_km, 2),
        avg_distance_per_order_km=round(total_km / len(assignments), 2) if assignments else 0.0,
        total_wait_minutes=round(sum(a.wait_minutes for a in assignments), 1),
        avg_slack_minutes=round(statistics.mean(slacks), 1) if slacks else 0.0,
        trucks_used=len(used),
        fleet_utilization=round(len(used) / len(available), 4) if available else 0.0,
        avg_capacity_utilization=round(
            statistics.mean(s.load_kg / s.truck.capacity_kg for s in used), 4) if used else 0.0,
        load_balance_stddev=round(statistics.pstdev(stop_counts), 3) if stop_counts else 0.0,
        objective_cost=round(objective, 2),
        rounds=rounds,
        runtime_ms=round(runtime_ms, 2),
    )


def _slacks(req: AllocationRequest, states: List[TruckState]):
    by_id = {o.id: o for o in req.orders}
    for s in states:
        for stop in s.stops:
            yield by_id[stop.order_id].window_end - stop.arrival


def make_assignment(
    order: Order, state: TruckState, ev: Evaluation, rnd: int, explanation: str,
    runner_up_id: Optional[str] = None, runner_up_delta: Optional[float] = None,
) -> Assignment:
    return Assignment(
        order_id=order.id, truck_id=state.truck.id, sequence=len(state.stops), round=rnd,
        cost=round(ev.cost, 3), distance_km=round(ev.distance_km, 3), eta=round(ev.arrival, 2),
        wait_minutes=round(ev.wait_minutes, 2), explanation=explanation,
        runner_up_truck_id=runner_up_id,
        runner_up_cost_delta=None if runner_up_delta is None else round(runner_up_delta, 3),
    )
