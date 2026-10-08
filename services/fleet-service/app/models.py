"""Fleet-service data contracts. These mirror the allocation-service schema
(microservices own their models; the JSON shape is the contract)."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator


class Capability(str, Enum):
    REFRIGERATED = "refrigerated"
    HAZMAT = "hazmat"
    LIFTGATE = "liftgate"
    FRAGILE = "fragile"


class Tightness(str, Enum):
    RELAXED = "relaxed"
    NORMAL = "normal"
    TIGHT = "tight"


class Location(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)


class Truck(BaseModel):
    id: str = ""
    name: str = ""
    depot: Location
    capacity_kg: float = Field(..., gt=0)
    capabilities: List[Capability] = Field(default_factory=list)
    shift_start: int = Field(480, ge=0, le=1440)
    shift_end: int = Field(1200, ge=0, le=1440)
    speed_kmh: float = Field(25.0, gt=0)
    max_stops: int = Field(8, ge=1)
    cost_per_km: float = Field(1.0, ge=0)
    available: bool = True

    @model_validator(mode="after")
    def _shift(self):
        if self.shift_end <= self.shift_start:
            raise ValueError("shift_end must be after shift_start")
        return self


class Order(BaseModel):
    id: str = ""
    customer: str = ""
    location: Location
    weight_kg: float = Field(..., gt=0)
    required_capabilities: List[Capability] = Field(default_factory=list)
    window_start: int = Field(..., ge=0, le=1440)
    window_end: int = Field(..., ge=0, le=1440)
    service_minutes: int = Field(10, ge=0)
    priority: int = Field(2, ge=1, le=3)

    @model_validator(mode="after")
    def _window(self):
        if self.window_end < self.window_start:
            raise ValueError("window_end must be >= window_start")
        return self


class Depot(BaseModel):
    id: str
    name: str
    location: Location


class City(BaseModel):
    id: str
    name: str
    center: Location
    radius_km: float


class GenerateRequest(BaseModel):
    name: Optional[str] = None
    city: str = "bengaluru"
    num_trucks: int = Field(12, ge=1, le=200)
    num_orders: int = Field(60, ge=1, le=1000)
    tightness: Tightness = Tightness.NORMAL
    seed: Optional[int] = None


class TruckPatch(BaseModel):
    available: Optional[bool] = None
    capacity_kg: Optional[float] = Field(None, gt=0)
    max_stops: Optional[int] = Field(None, ge=1)


class CreateScenarioRequest(BaseModel):
    """Create a scenario from the UI: empty, or with trucks/orders (e.g. imported JSON)."""
    name: str = Field(..., min_length=1, max_length=120)
    city: str = "bengaluru"
    trucks: List[Truck] = Field(default_factory=list)
    orders: List[Order] = Field(default_factory=list)


class Scenario(BaseModel):
    id: str
    name: str
    city: City
    seed: Optional[int] = None            # only for generated scenarios
    tightness: Optional[Tightness] = None  # only for generated scenarios
    created_at: datetime
    depots: List[Depot]
    trucks: List[Truck]
    orders: List[Order]


class ScenarioSummary(BaseModel):
    id: str
    name: str
    city: str
    num_trucks: int
    num_orders: int
    created_at: datetime
