"""Allocation strategies. Each exposes `allocate(request, truck_states)`."""
from . import greedy, hungarian

__all__ = ["greedy", "hungarian"]
