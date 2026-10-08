"""Each hard constraint rejects for the right reason; soft costs move the right way."""
from app import constraints as C
from app.constraints import TruckState, evaluate
from app.models import Capability, Weights

from .conftest import make_order, make_truck

W = Weights()


def ev(truck, order):
    return evaluate(TruckState.initial(truck), order, W, 1.3)


def test_feasible_basic():
    e = ev(make_truck("T"), make_order("O", 0.01))
    assert e.feasible and e.reason is None and e.distance_km > 0


def test_unavailable():
    assert ev(make_truck("T", available=False), make_order("O")).reason == C.UNAVAILABLE


def test_capability_required():
    order = make_order("O", required_capabilities=[Capability.REFRIGERATED])
    assert ev(make_truck("T"), order).reason == C.CAPABILITY
    assert ev(make_truck("T", capabilities=[Capability.REFRIGERATED]), order).feasible


def test_capacity():
    assert ev(make_truck("T", capacity_kg=40), make_order("O", weight_kg=50)).reason == C.CAPACITY


def test_time_window_late():
    # ~22 km away at 30 km/h from 08:00 -> cannot make an 08:10 deadline
    order = make_order("O", 0.15, window_start=480, window_end=490)
    assert ev(make_truck("T"), order).reason == C.TIME_WINDOW


def test_shift_end():
    order = make_order("O", 0.15, window_start=1150, window_end=1190)
    assert ev(make_truck("T", shift_end=1200), order).reason == C.SHIFT


def test_max_stops():
    truck = make_truck("T", max_stops=1)
    state = TruckState.initial(truck)
    o1, o2 = make_order("A", 0.01), make_order("B", 0.02)
    C.apply(state, o1, evaluate(state, o1, W, 1.3))
    assert evaluate(state, o2, W, 1.3).reason == C.MAX_STOPS


def test_waiting_is_penalised():
    early = ev(make_truck("T"), make_order("O", 0.01, window_start=480))
    late = ev(make_truck("T"), make_order("O", 0.01, window_start=700))
    assert late.wait_minutes > 200 and late.cost > early.cost


def test_over_qualification_penalised():
    plain = ev(make_truck("T"), make_order("O", 0.01))
    special = ev(make_truck("T", capabilities=[Capability.HAZMAT, Capability.REFRIGERATED]),
                 make_order("O", 0.01))
    assert special.over_qualification == 2
    assert special.cost - plain.cost == 2 * W.over_qualification


def test_apply_updates_state():
    truck = make_truck("T", capacity_kg=100)
    state = TruckState.initial(truck)
    order = make_order("O", 0.02, weight_kg=30, service_minutes=15)
    e = evaluate(state, order, W, 1.3)
    stop = C.apply(state, order, e)
    assert stop.sequence == 1
    assert state.remaining_capacity == 70
    assert state.time == e.service_start + 15
    assert state.position == order.location
