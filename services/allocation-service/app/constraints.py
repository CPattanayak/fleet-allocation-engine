"""Hard and soft constraints, evaluated against a truck's *current* route state.

Both algorithms share this module, so any difference in results comes purely
from the assignment strategy, not from different rules.

Hard constraints (an order is infeasible for a truck if any fails):
  * AVAILABILITY  - truck is active
  * CAPABILITY    - truck has every capability the order requires
  * CAPACITY      - remaining payload >= order weight
  * MAX_STOPS     - truck route has room for another stop
  * TIME_WINDOW   - truck arrives no later than window_end
  * SHIFT         - after service the truck can return to its depot before shift_end

Soft constraints (contribute to cost, in km-equivalents):
  * distance           - deadhead km from the truck's last position
  * waiting            - idle minutes before the window opens
  * over_qualification - special capabilities 'burned' on an order that doesn't need them
  * load_balance       - discourages piling every order onto one truck
  * lateness_risk      - arriving with little slack before the window closes
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from .geo import road_km, travel_minutes
from .models import Location, Order, Stop, Truck, Weights

SLACK_COMFORT_MIN = 30.0

# Rejection reason codes (used in explanations / unassigned reports)
UNAVAILABLE = "truck_unavailable"
CAPABILITY = "missing_capability"
CAPACITY = "insufficient_capacity"
MAX_STOPS = "route_full"
TIME_WINDOW = "would_arrive_late"
SHIFT = "exceeds_shift"


@dataclass
class TruckState:
    """Mutable route state of one truck during allocation."""

    truck: Truck
    position: Location
    time: float
    load_kg: float = 0.0
    distance_km: float = 0.0
    stops: List[Stop] = field(default_factory=list)

    @classmethod
    def initial(cls, truck: Truck) -> "TruckState":
        return cls(truck=truck, position=truck.depot, time=float(truck.shift_start))

    @property
    def remaining_capacity(self) -> float:
        return self.truck.capacity_kg - self.load_kg


@dataclass
class Evaluation:
    feasible: bool
    reason: Optional[str]
    cost: float = 0.0
    distance_km: float = 0.0
    arrival: float = 0.0
    service_start: float = 0.0
    departure: float = 0.0
    wait_minutes: float = 0.0
    slack_minutes: float = 0.0
    over_qualification: int = 0


def evaluate(state: TruckState, order: Order, weights: Weights, road_factor: float) -> Evaluation:
    """Check hard constraints and, if feasible, compute the soft cost of
    appending `order` to the end of `state`'s route."""
    truck = state.truck
    if not truck.available:
        return Evaluation(False, UNAVAILABLE)
    if not set(order.required_capabilities).issubset(truck.capabilities):
        return Evaluation(False, CAPABILITY)
    if order.weight_kg > state.remaining_capacity + 1e-9:
        return Evaluation(False, CAPACITY)
    if len(state.stops) >= truck.max_stops:
        return Evaluation(False, MAX_STOPS)

    km = road_km(state.position, order.location, road_factor)
    arrival = state.time + travel_minutes(km, truck.speed_kmh)
    if arrival > order.window_end + 1e-9:
        return Evaluation(False, TIME_WINDOW)

    service_start = max(arrival, float(order.window_start))
    departure = service_start + order.service_minutes
    back_km = road_km(order.location, truck.depot, road_factor)
    if departure + travel_minutes(back_km, truck.speed_kmh) > truck.shift_end + 1e-9:
        return Evaluation(False, SHIFT)

    wait = service_start - arrival
    slack = order.window_end - arrival
    over_q = len(set(truck.capabilities) - set(order.required_capabilities))

    cost = (
        weights.distance * km * truck.cost_per_km
        + weights.waiting * wait
        + weights.over_qualification * over_q
        + weights.load_balance * len(state.stops)
        + weights.lateness_risk * max(0.0, SLACK_COMFORT_MIN - slack)
    )
    return Evaluation(
        True, None, cost=cost, distance_km=km, arrival=arrival, service_start=service_start,
        departure=departure, wait_minutes=wait, slack_minutes=slack, over_qualification=over_q,
    )


def apply(state: TruckState, order: Order, ev: Evaluation) -> Stop:
    """Commit an evaluated order to the truck's route."""
    stop = Stop(
        order_id=order.id,
        sequence=len(state.stops) + 1,
        arrival=round(ev.arrival, 2),
        service_start=round(ev.service_start, 2),
        departure=round(ev.departure, 2),
        distance_from_prev_km=round(ev.distance_km, 3),
        location=order.location,
    )
    state.stops.append(stop)
    state.position = order.location
    state.time = ev.departure
    state.load_kg += order.weight_kg
    state.distance_km += ev.distance_km
    return stop


def unassigned_cost(order: Order, weights: Weights) -> float:
    return weights.unassigned_penalty * order.priority
