"""Domain model for the delivery-fleet allocation problem.

Times are expressed as *minutes since midnight* (e.g. 480 == 08:00) so that
arithmetic stays trivial and JSON stays readable.
"""
from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, model_validator


class Capability(str, Enum):
    REFRIGERATED = "refrigerated"
    HAZMAT = "hazmat"
    LIFTGATE = "liftgate"
    FRAGILE = "fragile"


class Algorithm(str, Enum):
    GREEDY = "greedy"
    HUNGARIAN = "hungarian"


class Location(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)


class Truck(BaseModel):
    """A mobile resource: one truck with a driver and a shift."""

    id: str
    name: str = ""
    depot: Location
    capacity_kg: float = Field(..., gt=0)
    capabilities: List[Capability] = Field(default_factory=list)
    shift_start: int = Field(480, ge=0, le=1440)
    shift_end: int = Field(1200, ge=0, le=1440)
    speed_kmh: float = Field(30.0, gt=0)
    max_stops: int = Field(8, ge=1)
    cost_per_km: float = Field(1.0, ge=0)
    available: bool = True

    @model_validator(mode="after")
    def _check_shift(self) -> "Truck":
        if self.shift_end <= self.shift_start:
            raise ValueError("shift_end must be after shift_start")
        return self


class Order(BaseModel):
    """A delivery request."""

    id: str
    customer: str = ""
    location: Location
    weight_kg: float = Field(..., gt=0)
    required_capabilities: List[Capability] = Field(default_factory=list)
    window_start: int = Field(..., ge=0, le=1440)
    window_end: int = Field(..., ge=0, le=1440)
    service_minutes: int = Field(10, ge=0)
    priority: int = Field(2, ge=1, le=3, description="1=low, 2=normal, 3=urgent")

    @model_validator(mode="after")
    def _check_window(self) -> "Order":
        if self.window_end < self.window_start:
            raise ValueError("window_end must be >= window_start")
        return self


class Weights(BaseModel):
    """Soft-constraint weights. All costs are in 'km-equivalents'."""

    distance: float = Field(1.0, ge=0, description="per km of deadhead driving")
    waiting: float = Field(0.2, ge=0, description="per minute a truck idles before a window opens")
    over_qualification: float = Field(3.0, ge=0, description="per special capability 'wasted' on an order that doesn't need it")
    load_balance: float = Field(0.5, ge=0, description="per order already on the truck's route")
    lateness_risk: float = Field(0.05, ge=0, description="per minute of lost slack below 30 min to the window close")
    unassigned_penalty: float = Field(500.0, gt=0, description="cost of leaving an order unserved, x priority")


class AllocationRequest(BaseModel):
    trucks: List[Truck]
    orders: List[Order]
    algorithm: Algorithm = Algorithm.GREEDY
    weights: Weights = Field(default_factory=Weights)
    road_factor: float = Field(1.3, ge=1.0, le=3.0, description="road distance / straight-line distance")
    single_stop: bool = Field(False, description="If true each truck takes at most one order (pure bipartite matching)")
    hungarian_wait_horizon: Optional[float] = Field(
        60, ge=0, le=720,
        description="Hungarian only: per round, only match pairs where the truck idles <= this many minutes "
                    "(falls back to unrestricted when nothing fits). null = pure batched matching. Ignored in single_stop mode.")


class Stop(BaseModel):
    order_id: str
    sequence: int
    arrival: float
    service_start: float
    departure: float
    distance_from_prev_km: float
    location: Location


class Assignment(BaseModel):
    order_id: str
    truck_id: str
    sequence: int
    round: int
    cost: float
    distance_km: float
    eta: float
    wait_minutes: float
    explanation: str
    runner_up_truck_id: Optional[str] = None
    runner_up_cost_delta: Optional[float] = None


class UnassignedOrder(BaseModel):
    order_id: str
    reason: str
    rejections: Dict[str, int] = Field(default_factory=dict)


class TruckRoute(BaseModel):
    truck_id: str
    stops: List[Stop]
    total_distance_km: float
    return_distance_km: float
    load_kg: float
    capacity_kg: float
    end_time: float


class Metrics(BaseModel):
    total_orders: int
    assigned_orders: int
    unassigned_orders: int
    fulfillment_rate: float
    priority_weighted_fulfillment: float
    urgent_fulfillment: float
    total_distance_km: float
    avg_distance_per_order_km: float
    total_wait_minutes: float
    avg_slack_minutes: float
    trucks_used: int
    fleet_utilization: float
    avg_capacity_utilization: float
    load_balance_stddev: float
    objective_cost: float
    rounds: int
    runtime_ms: float


class AllocationResult(BaseModel):
    algorithm: Algorithm
    assignments: List[Assignment]
    unassigned: List[UnassignedOrder]
    routes: List[TruckRoute]
    metrics: Metrics
