# Greedy vs Hungarian — what the comparison taught me

All numbers come from `python scripts/benchmark.py` (full tables in
[`docs/benchmark_results.md`](docs/benchmark_results.md)): 8 seeded Bengaluru scenarios per row,
fleet sizes 5–50 trucks, 20–300 orders, three time-window tightness levels. Both strategies share
**the same constraint module and the same cost function**, so every difference is caused by the
assignment strategy alone.

Three variants are compared:

| Label | Strategy |
|---|---|
| **G** | Greedy: urgent first, then earliest deadline; each order goes to the truck with the lowest marginal cost of appending it. Never revisits. |
| **H** | Pure batched Hungarian: each round is one global min-cost matching (≤ 1 new stop per truck), repeated until nothing changes. |
| **H60** | Batched Hungarian with a 60-minute look-ahead: a round only matches pairs where the truck idles ≤ 60 min (falls back to unrestricted when nothing fits). This is the default. |

The **objective** is the quantity both algorithms try to minimise: soft cost of every assignment
(km, idle minutes, wasted special capability, load balance, lateness risk) plus a priority-scaled
penalty for every unserved order.

---

## 1. When the problem *is* a matching, Hungarian always wins — and greedy is surprisingly far off

In single-stop mode (each truck takes at most one order — e.g. "dispatch the next job"), the problem
is exactly a weighted bipartite matching and Hungarian is provably optimal.

* Hungarian achieved the best objective in **72 / 72** scenarios.
* It drove **13–25 % fewer km** for the same or more orders (e.g. 40/60: 627 → 518 km).
* Priority-weighted fulfilment was equal or better everywhere.

Why greedy loses: it fixes the most urgent order first and hands it the nearest truck, even when that
truck is the *only* good option for another order and a slightly worse truck would have done for the
first. The unit test `test_hungarian_beats_greedy_on_trap` reproduces this with two trucks and two
orders, and the Hungarian explanation for that order literally says *"Locally cheapest was A … but
A was worth more serving O2"*.

## 2. Pure batched Hungarian is *not* automatically better on routing — it is time-blind

Real trucks do multi-stop routes with time windows. Here the naive "repeat the matching" approach
gave a split verdict:

| Scenario | Objective G | Objective H | |
|---|---|---|---|
| 25 trucks / 150 orders, relaxed | 18 217 | **10 746** | H −41 %, fulfilment 85.8 % → 93.3 % |
| 50 / 300, relaxed | 23 157 | **11 245** | H −51 %, fulfilment 90.3 % → 97.2 % |
| 12 / 60, tight | **9 265** | 11 517 | H +24 %, fulfilment 83.3 % → 75.8 % |
| 25 / 150, tight | **19 176** | 23 598 | H +23 %, fulfilment 85.6 % → 80.3 % |

The cause is visible in the idle-wait column: H trucks idle **55–85 % longer** than greedy ones.
In round 1 every truck is at its depot at 08:00 and the matching only sees *cost*, not *sequence*. If
a 15:00 order is cheap in kilometres, a truck gets it in round 1, its clock jumps to 15:00 and every
morning order it could have done becomes infeasible. Waiting is only a soft cost; the matching
happily pays it. Greedy's earliest-deadline ordering is an implicit time-sweep, which is exactly what
tight windows reward.

**Lesson:** "global" optimality is only global *within the model each step sees*. A batch method
that optimises one stop at a time can be worse than a myopic method whose processing order carries
the right structural insight.

## 3. A small domain fix — look-ahead — makes batch matching dominant

Restricting each round to work a truck can start within 60 minutes turns the rounds into a rolling
horizon: trucks are matched to near-term work first, and the afternoon is planned once they get
there. Results (best-objective count across 8 seeds in brackets):

| Scenario | G | H | H60 |
|---|---|---|---|
| 12 / 60 normal | 9 344 (0) | 9 432 (0) | **6 976 (8)** |
| 12 / 60 tight | 9 265 (2) | 11 517 (0) | **8 515 (6)** |
| 25 / 150 tight | 19 176 (0) | 23 598 (0) | **11 269 (8)** |
| 50 / 300 normal | 27 175 (0) | 19 881 (1) | **12 416 (7)** |
| 50 / 300 tight | 30 911 (0) | 30 951 (0) | **15 321 (8)** |

On the 50 / 300 tight day H60 serves **95.8 %** of orders versus 87 % for both other variants.
The look-ahead is still not a silver bullet: on very relaxed large instances the pure version is
slightly better (11 245 vs 11 751 on 50/300 relaxed), because there the horizon only removes options.

**The trade-off it makes:** H60 usually drives more km per order than greedy (typically 5–25 % more, e.g. 9.2 → 11.8 km on 50/300 tight). With the default
weights an unserved order costs 500 × priority, so the optimiser correctly prefers a longer drive
to a missed delivery. Lower the *Unserved penalty* slider in the UI and the balance moves back
towards distance — the weights are a business decision, not an algorithm property.

## 4. When does the difference matter most?

* **Contention.** With 5 trucks / 20 orders greedy had the best objective in 5 of 8 seeds — when
  each order only has one or two plausible trucks, there is little for a global view to fix. The gap
  opens with fleet size: at 25+ trucks the batch method won in almost every seed.
* **Scarcity and priorities.** When the fleet cannot serve everything, the dummy "leave unserved"
  columns let Hungarian decide *which* orders to drop as part of the optimisation; greedy drops
  whatever is left at the end.
* **Time structure.** Tight windows punish any method that ignores sequence. Either process in
  deadline order (greedy) or constrain the batch to a time horizon (H60).

## 5. Cost of the global view

| | 12 / 60 | 25 / 150 | 50 / 300 |
|---|---|---|---|
| Greedy | ~3 ms | ~12 ms | ~45–50 ms |
| Hungarian (SciPy) | ~9–16 ms | ~47–64 ms | ~210–270 ms |

Greedy is O(n·m). Each Hungarian round builds an n × (m + n) cost table and solves it with SciPy's
`linear_sum_assignment` (roughly cubic in the table size), for up to `max_stops` rounds. Using a
well-tested library instead of a hand-written solver keeps the code short and fast; the tests check
that the way we build the table (including the "skip" columns) gives the same answer as trying every
possible plan. Both strategies are comfortably fast for batch dispatch; for a stream of single orders
arriving in real time, greedy insertion remains the natural fit.

## 6. Practical recommendation

| Situation | Choice |
|---|---|
| Orders arrive one by one, decision needed in milliseconds | Greedy (optionally re-optimise in batch every few minutes) |
| Assign the *next* job to each idle driver | Hungarian, single-stop mode — it is optimal |
| Plan the day for a medium/large fleet | Hungarian with look-ahead |
| Small fleet, few alternatives per order | Either; greedy is simpler to explain |

## 7. What I would do next

1. Insert orders anywhere in a route (cheapest insertion), not only append — both strategies would gain.
2. A local-search pass (2-opt / relocate) on top of either result.
3. Real road distances and traffic-aware travel times via a self-hosted OSRM.
4. Tune the soft-constraint weights from historical outcomes (the ML option from the brief).
