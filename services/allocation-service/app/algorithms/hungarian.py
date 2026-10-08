"""Hungarian allocation, done in rounds.

The idea in plain words:
  1. Make a price table: every waiting order against every truck.
  2. Let SciPy pick the cheapest overall pairing (each truck gets at most one order).
  3. Give those orders to those trucks. The trucks move on and their clocks go forward.
  4. Repeat with the orders that are still waiting, until nothing more fits.

Two extra ideas:
  * "Skip" columns - every order can also be skipped this round, at a price of
    500 x priority. So if there aren't enough trucks, low-priority orders wait first.
  * Look-ahead (default 60 min) - a round only looks at jobs a truck can start
    within the next hour. Without it a truck can get a 3 PM job at 8 AM just
    because it's close by, and then miss all its morning work. If nothing fits
    in the hour, we try again without the limit so later orders still get served.

With one order per truck (single_stop) there is only one round, and the answer
is the best possible one.
"""
from __future__ import annotations

import time
from typing import List

import numpy as np
from scipy.optimize import linear_sum_assignment

from ..constraints import TruckState, apply, evaluate, unassigned_cost
from ..models import AllocationRequest, AllocationResult
from .common import build_result, describe_choice, make_assignment

# Price we put in the table for "this truck can't take this order".
# It's so big that SciPy will never choose it.
NOT_ALLOWED = 1e9


# --------------------------------------------------------------------------
# Main function
# --------------------------------------------------------------------------
def allocate(req: AllocationRequest, trucks: List[TruckState]) -> AllocationResult:
    start_time = time.perf_counter()

    waiting = sorted(req.orders, key=lambda o: o.id)   # sorted so every run gives the same answer
    assignments = []
    round_no = 0

    while waiting and trucks:
        # what would each order cost with each truck, from where the trucks are right now?
        prices = price_every_pair(waiting, trucks, req)

        # find this round's pairs (tries the 60-min look-ahead first)
        pairs, truck_to_order, look_ahead = pick_pairs(waiting, prices, trucks, req)
        if not pairs:
            break                        # no truck can take any order - stop here

        round_no += 1
        for order_index, truck_index in pairs:
            order = waiting[order_index]
            truck = trucks[truck_index]
            price = prices[order_index][truck_index]

            why, runner_up, runner_up_diff = explain(round_no, order_index, truck_index, prices,
                                                     trucks, waiting, truck_to_order, look_ahead)
            why += describe_choice(order, truck, price)   # must run before apply(), it reads the old load

            apply(truck, order, price)                    # truck drives there; clock, load and position update
            assignments.append(make_assignment(order, truck, price, round_no, why, runner_up, runner_up_diff))

        waiting = remove_assigned(waiting, pairs)

    not_served = [o.id for o in waiting]
    runtime_ms = (time.perf_counter() - start_time) * 1000
    return build_result(req, trucks, assignments, not_served, rounds=round_no, runtime_ms=runtime_ms)


# --------------------------------------------------------------------------
# Step 1 - prices
# --------------------------------------------------------------------------
def price_every_pair(waiting, trucks, req):
    """prices[o][t] = what happens if truck t takes order o (allowed? cost? wait?)."""
    prices = []
    for order in waiting:
        row = []
        for truck in trucks:
            row.append(evaluate(truck, order, req.weights, req.road_factor))
        prices.append(row)
    return prices


def can_take(price, look_ahead):
    """Truck is allowed to take the order, and (if look-ahead is on) won't wait too long."""
    if not price.feasible:
        return False
    if look_ahead is not None and price.wait_minutes > look_ahead:
        return False
    return True


# --------------------------------------------------------------------------
# Step 2 - pick the pairs
# --------------------------------------------------------------------------
def pick_pairs(waiting, prices, trucks, req):
    """Try with the look-ahead first; if that gives nothing, try again without it."""
    look_ahead = req.hungarian_wait_horizon
    pairs, truck_to_order = solve_one_round(waiting, prices, len(trucks), req, look_ahead)

    if not pairs and look_ahead is not None:
        look_ahead = None
        pairs, truck_to_order = solve_one_round(waiting, prices, len(trucks), req, look_ahead)

    return pairs, truck_to_order, look_ahead


def solve_one_round(waiting, prices, num_trucks, req, look_ahead):
    """Build the price table, let SciPy solve it, and read the answer back."""
    table = build_table(waiting, prices, num_trucks, req, look_ahead)

    # SciPy gives back two lists: row numbers, and the column it picked for each row.
    rows, cols = linear_sum_assignment(np.array(table))

    pairs = []            # (order_index, truck_index) to hand out this round
    truck_to_order = {}   # which order each truck got - only used for the explanation text
    for order_index, column in zip(rows, cols):
        order_index, column = int(order_index), int(column)
        if column >= num_trucks:
            continue      # SciPy picked a "skip" column - this order waits for the next round
        truck_to_order[column] = order_index
        if can_take(prices[order_index][column], look_ahead):   # just in case - never hand out a blocked pair
            pairs.append((order_index, column))
    return pairs, truck_to_order


def build_table(waiting, prices, num_trucks, req, look_ahead):
    """One row per order.
    Columns: one per truck, then one "skip" column per order.

                 T1     T2    skip   skip   skip
        O1   [   5,     7,    1000,  1000,  1000 ]
        O2   [   4,  1e9,     1500,  1500,  1500 ]    <- O2 is urgent, so skipping costs more
        O3   [ 1e9,  1e9,     1000,  1000,  1000 ]    <- nobody can take O3 right now
    """
    table = []
    for order_index, order in enumerate(waiting):
        row = []
        for truck_index in range(num_trucks):
            price = prices[order_index][truck_index]
            row.append(price.cost if can_take(price, look_ahead) else NOT_ALLOWED)

        skip_price = unassigned_cost(order, req.weights)    # 500 x priority by default
        row.extend([skip_price] * len(waiting))             # enough skip columns for every order
        table.append(row)
    return table


# --------------------------------------------------------------------------
# Step 3 - bookkeeping
# --------------------------------------------------------------------------
def remove_assigned(waiting, pairs):
    """Orders that got a truck this round are done; the rest wait for the next round."""
    done = {order_index for order_index, _ in pairs}
    return [order for i, order in enumerate(waiting) if i not in done]


def explain(round_no, order_index, truck_index, prices, trucks, waiting, truck_to_order, look_ahead):
    """Text for the UI saying why this order got this truck.
    Also returns the runner-up truck and how much more (or less) it would have cost."""
    price = prices[order_index][truck_index]

    text = f"Round {round_no}: global matching of {len(waiting)} pending order(s) x {len(trucks)} truck(s)"
    text += f" within a {look_ahead:.0f}-min look-ahead. " if look_ahead is not None else ". "

    # every truck that could have taken this order, cheapest first
    options = []
    for t, p in enumerate(prices[order_index]):
        if can_take(p, look_ahead):
            options.append((p.cost, trucks[t].truck.id, t))
    options.sort()
    cheapest_cost, cheapest_id, cheapest_index = options[0]

    if cheapest_index != truck_index:
        # this order did NOT get its cheapest truck - say who got that truck instead
        if cheapest_index in truck_to_order:
            other = waiting[truck_to_order[cheapest_index]].id
            reason = f"{cheapest_id} was worth more serving {other}"
        else:
            reason = "the global optimum differed"
        text += (f"Locally cheapest was {cheapest_id} (cost {cheapest_cost:.1f} vs {price.cost:.1f}), "
                 f"but {reason} - the matching minimises total cost, not this order's cost. ")
        return text, cheapest_id, cheapest_cost - price.cost

    # it did get its cheapest truck
    text += f"Also this order's locally cheapest truck (cost {price.cost:.1f}). "
    if len(options) > 1:
        return text, options[1][1], options[1][0] - price.cost
    return text, None, None