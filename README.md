# Fleet Allocation Engine — delivery trucks × orders

A resource allocation engine for a **delivery fleet**: trucks with payloads, special capabilities
and shifts are assigned to delivery orders with weights, requirements, priorities and time windows.
Two strategies — **Greedy** and **batched Hungarian** (solved with SciPy) — run on identical constraints
and are visualised separately and side by side in a React + Redux web app.

* **Backend:** 3 FastAPI microservices (gateway, fleet data, allocation)
* **Frontend:** React 18 + Redux Toolkit + React Router, bundled with **Webpack 5**, map with Leaflet + OpenStreetMap
* **Ops:** a Dockerfile per service, `docker-compose.yml`, nginx in front of the UI
* **Docs:** this README and [ANALYSIS.md](ANALYSIS.md) (what the comparison showed), benchmark tables in [docs/benchmark_results.md](docs/benchmark_results.md)

No paid services and no API keys. The only network use is loading OpenStreetMap tiles in the browser.

**Contents:** [Quick start](#quick-start-docker) · [Running without Docker](#running-without-docker) ·
[Tests](#tests) · [Approach](#approach-in-brief) · [Architecture](#architecture) ·
[Algorithms](#algorithms) · [The UI](#the-ui) · [Brief analysis](#brief-analysis--what-i-learned) ·
[Limitations](#design-decisions--limitations)

## Approach in brief

1. **Model the problem.** Trucks (resources) and orders (requests) each carry the attributes that
   matter for delivery: payload, special equipment, shift, speed and stop limit for trucks; weight,
   required equipment, time window and priority for orders.
2. **One rulebook, two strategies.** A single `constraints.evaluate()` decides whether a truck *may*
   take an order (hard constraints) and how much it *costs* (soft constraints). Greedy and Hungarian
   both call it, so any difference in their results comes only from how they assign.
3. **Greedy:** take orders one by one (urgent first, then earliest deadline) and give each to the
   cheapest allowed truck.
4. **Hungarian:** in rounds, build a cost table of *all* waiting orders × trucks (plus a "skip" option
   per order) and let SciPy's `linear_sum_assignment` find the cheapest overall pairing.
5. **Explain every decision** in plain text, and report why any order was left unserved.
6. **Measure** both on the same scenarios (UI Compare tab plus an offline benchmark) and write up the
   findings.
7. **Split into services:** data (fleet-service), optimisation (allocation-service) and a gateway for
   the UI, each in its own Docker container.

---

## Quick start (Docker)

```bash
docker compose up --build
```

| URL | What |
|---|---|
| http://localhost:3000 | Web UI |
| http://localhost:8000/docs | API gateway (OpenAPI) |
| http://localhost:8001/docs | fleet-service |
| http://localhost:8002/docs | allocation-service |

The app starts **empty**: create a scenario from the UI (empty, random, or import JSON), then add trucks and
orders on the **Setup** tab. To preload two demo scenarios instead, set `SEED_DEFAULT_SCENARIO="true"`
for fleet-service in `docker-compose.yml`.

## Running without Docker

Requires Python 3.11+ and Node 18+.

```bash
# 1. Python services (one virtualenv is fine for all three)
python -m venv .venv && source .venv/bin/activate
pip install -r services/allocation-service/requirements-dev.txt \
            -r services/fleet-service/requirements-dev.txt \
            -r services/api-gateway/requirements-dev.txt

# 2. Frontend
cd frontend && npm install && cd ..

# 3. Start everything (fleet :8001, allocation :8002, gateway :8000, UI :3000)
./scripts/dev.sh
```

Or start pieces by hand, e.g. `cd services/allocation-service && uvicorn app.main:app --port 8002`.
The webpack dev server (`npm start`) proxies `/api` to `http://localhost:8000` (override with `API_TARGET`).
`npm run build` produces the production bundle in `frontend/dist`.

## Tests

```bash
./scripts/test_all.sh
```

| Suite | Tests | Covers |
|---|---|---|
| allocation-service | 108 | Hungarian (SciPy + skip columns) matches brute-force optimum; every hard constraint; greedy tie-breaking; replay-validation of every route from both algorithms on random scenarios; greedy-trap case where Hungarian provably wins; Hungarian ≤ greedy in single-stop mode; look-ahead behaviour; API |
| fleet-service | 7 | Deterministic generator, create empty / imported scenarios, add / edit / remove trucks and orders, validation |
| api-gateway | 6 | Orchestration, per-metric winner summary, error propagation, 502 when a service is down, POST/PUT proxying (mocked transports) |
| frontend (Jest) | 14 | Redux reducers (results invalidation, selection, scenario create/delete), time formatting, disagreement diff |

Each Dockerfile also has a `test` stage: `docker build --target test services/allocation-service`.
The frontend image runs Jest before building.

**Benchmark** (offline, no servers needed — regenerates `docs/benchmark_results.md`):

```bash
python scripts/benchmark.py          # full sweep, ~20 s
python scripts/benchmark.py --quick
```

---

## Architecture

```
                 ┌──────────────────────────┐
  Browser ─────▶ │ frontend (nginx :3000)   │  React + Redux SPA, Webpack bundle
                 │  /api/* ─┐               │
                 └──────────┼───────────────┘
                            ▼
                 ┌──────────────────────────┐
                 │ api-gateway (:8000)      │  single entry point, CORS, health aggregation,
                 │                          │  orchestration, runs /compare in parallel
                 └──────┬─────────────┬─────┘
            scenarios   │             │  trucks + orders + options
                        ▼             ▼
       ┌────────────────────┐   ┌───────────────────────────┐
       │ fleet-service      │   │ allocation-service        │
       │ (:8001)            │   │ (:8002)                   │
       │ scenario generator │   │ stateless optimiser:      │
       │ trucks/orders CRUD │   │ constraints, Greedy,      │
       │ in-memory store    │   │ Hungarian, explanations,  │
       └────────────────────┘   │ metrics                   │
                                └───────────────────────────┘
```

* **fleet-service** owns data. Scenarios are generated deterministically from a seed; the store is an
  in-memory repository behind a small interface (swap for Postgres without touching the API).
* **allocation-service** is pure computation — stateless, so it scales horizontally and is trivially testable.
* **api-gateway** keeps the UI ignorant of service topology: it loads a scenario, forwards it to the
  optimiser, and for `/api/compare` runs both algorithms concurrently and adds a per-metric winner summary.

### Main endpoints (gateway)

| Method & path | Purpose |
|---|---|
| `GET /api/health` | Gateway + downstream health |
| `GET /api/cities`, `GET /api/algorithms` | Metadata |
| `GET/POST/PUT/PATCH/DELETE /api/scenarios…` | Proxied to fleet-service: list, get, `POST /scenarios` (empty or with trucks/orders), `POST /generate`, add / edit (`PUT`) / patch / remove trucks, add / edit / remove orders, `POST /{id}/orders/random?count=` |
| `POST /api/allocate` | `{scenario_id, algorithm, weights?, road_factor?, single_stop?, hungarian_wait_horizon?}` |
| `POST /api/compare` | Same options; returns both results + per-metric winners |

---

## Domain model

| Entity | Key fields |
|---|---|
| **Truck** (resource) | depot location, `capacity_kg`, `capabilities` (refrigerated, hazmat, liftgate, fragile), shift start/end, speed, `max_stops`, cost per km, `available` |
| **Order** (request) | location, `weight_kg`, `required_capabilities`, time window, service minutes, priority 1–3 |
| **Assignment** | order ↔ truck, stop sequence, ETA, wait, cost, round, **natural-language explanation**, runner-up truck & cost delta |
| **TruckRoute** | ordered stops with arrival/service/departure times, distance incl. return to depot, load |

Times are minutes since midnight. Distance is haversine × a road factor (default 1.3) — no routing API.

### Constraints

Both algorithms call the same `constraints.evaluate(truck_state, order)`, which checks feasibility of
appending the order to the truck's current route and prices it.

**Hard** (reject): truck available · has all required capabilities · remaining payload ≥ weight ·
route has room (`max_stops`) · arrives before the window closes · can serve and still return to depot
before shift end.

**Soft** (cost in km-equivalents, weights adjustable live in the UI):
deadhead km × cost/km · idle minutes before the window opens · special capabilities "wasted" on an
order that doesn't need them (keeps reefers free for cold orders) · stops already on the truck
(load balance) · arriving with < 30 min slack · and a priority-scaled penalty for leaving an order unserved.

### Algorithms

**Greedy.** Sort orders by priority, then earliest window close (EDF). For each, evaluate every truck
and append the order to the feasible truck with the lowest marginal cost. O(n·m), never revisits.
Trucks within 0.05 of the best cost count as tied; the lowest truck ID wins (repeatable results) and
the explanation says it was a tie.

**Batched Hungarian.** Each round builds a matrix *pending orders × (trucks + one "leave unserved"
dummy column per order)*: feasible cells hold the soft cost, infeasible cells a prohibitive value,
dummy cells the order's unserved penalty. SciPy's `linear_sum_assignment` finds the minimum-cost matching (≤ 1 new stop
per truck); matches are committed, truck clocks/positions advance and the next round re-plans.
The dummy columns make every round solvable and let the optimiser choose which orders to drop
when the fleet is over-subscribed.
*Look-ahead* (default 60 min): a round only matches pairs where the truck would idle ≤ the horizon,
retrying unrestricted if nothing fits — this fixes batch matching's blindness to time order
(see [ANALYSIS.md](ANALYSIS.md)). *Single-stop mode* runs one round with no horizon, which is exactly
optimal. The matching itself is done by `scipy.optimize.linear_sum_assignment`, a well-tested
library function, so the project code only has to build the cost table and read the answer.

**Explanations.** Every assignment says why: distance, ETA vs window, slack, payload, waiting,
capabilities, runner-up and cost delta; Hungarian additionally reports when it overrode an order's
locally cheapest truck and which order needed that truck more. Unserved orders list how many trucks
failed each hard constraint (e.g. *"No feasible truck: 18 lack a required capability, 4 would arrive
after the window closes"*).

### Metrics

Fulfilment rate · priority-weighted and urgent fulfilment · total km and km per order (incl. return
legs) · idle waiting · average slack to deadline · trucks used and capacity utilisation · σ of stops
per truck · objective cost · rounds · runtime.

---

## The UI

Tabs along the top:

| Tab | |
|---|---|
| **Setup** | Build the scenario by hand. Click the map to pick a location, fill in the truck or order form (capacity, shift, capabilities, time window, priority…), and add it. Every row can be edited, taken off duty or removed. Export the scenario as JSON. |
| **Greedy** | Greedy result only: how it works, metric tiles, map with routes, per-truck route cards, decision log with explanations, unassigned orders with reasons. |
| **Hungarian** | The same views for the Hungarian result. |
| **Compare** | Both maps side by side, metrics won, metric table with deltas, and every order the two strategies decided differently. |

The tab badges show the scenario size and how many orders each algorithm served. When there are no
scenarios, a welcome screen offers three ways to start: **Empty**, **Random** (generated test data) or
**Import JSON** (a file exported from Setup). The sidebar holds the scenario picker and the
soft-constraint sliders. Changing the data or switching scenario clears old results, and each algorithm
tab re-runs when you open it.

## Brief analysis — what I learned

Full write-up with all numbers: [ANALYSIS.md](ANALYSIS.md). Raw tables: [docs/benchmark_results.md](docs/benchmark_results.md)
(8 seeded scenarios per row, 5–50 trucks, 20–300 orders, relaxed / normal / tight time windows).

1. **When it is a pure matching problem, Hungarian always wins.** With one order per truck, Hungarian
   had the best result in **72 of 72** scenarios and drove **13–25 % fewer km**. Greedy gives the
   nearest truck to the first order even when another order needed that truck more.
2. **Plain "repeat the matching" Hungarian ignores time.** On real multi-stop days it can do *worse*
   than Greedy: about **+23 % cost** on tight time windows. In round 1 it hands a truck an afternoon
   job because it is close by, and the truck then misses its morning work. Greedy's earliest-deadline
   order is an implicit time sweep, which is exactly what tight windows reward.
3. **A small domain fix makes batch matching the best option.** Limiting each round to work a truck
   can start within **60 minutes** (the look-ahead) gave the lowest cost in most medium and large
   scenarios. On the 50-truck / 300-order tight day it roughly **halved** Greedy's cost and served
   **95.8 %** of orders versus **87 %**.
4. **Size matters.** With 5 trucks / 20 orders, Greedy was best in 5 of 8 seeds, since there is little
   for a global view to fix. From about 25 trucks up, batch matching won almost every seed.
5. **There is a trade-off.** The look-ahead version drives more km per order because missing a
   delivery is penalised far more than extra driving. The sliders in the UI move that balance:
   weights are a business choice, not a property of the algorithm.
6. **Speed is not a problem.** For 300 orders Greedy takes about 0.05 s and Hungarian (SciPy) about 0.25 s.

**Which one to use:**

| Situation | Better choice |
|---|---|
| Orders arrive one at a time and need an answer instantly | Greedy |
| Each idle driver needs their next job at the same moment | Hungarian, one-order-per-truck mode (optimal) |
| Planning a full day for a medium or large fleet | Hungarian with look-ahead |
| Small fleet, few alternatives per order | Either; Greedy is simpler to explain |

A practical setup combines them: Greedy for instant answers as orders arrive, and a Hungarian
re-plan every 10–15 minutes over the orders not yet picked up.

## Project layout

```
docker-compose.yml
services/
  api-gateway/         app/main.py, tests/, Dockerfile, requirements*.txt
  fleet-service/       app/{main,models,generator,store}.py, tests/, Dockerfile
  allocation-service/  app/{main,models,engine,constraints,geo}.py
                       app/algorithms/{greedy,hungarian,common}.py, tests/, Dockerfile
frontend/              webpack.config.js, babel.config.json, nginx.conf, Dockerfile
  src/{api,store,components,pages,utils}/, src/__tests__/
scripts/               benchmark.py, test_all.sh, dev.sh
docs/benchmark_results.md
ANALYSIS.md
```

## Design decisions & limitations

* **Append-only routing.** Both strategies extend a truck's route at the end; neither inserts in the
  middle or re-orders stops. This keeps the comparison about *assignment*, and is the first thing I would
  improve (cheapest insertion + 2-opt).
* **Straight-line × road factor** instead of a road network keeps the system offline and keyless.
* **In-memory fleet store**: restarting fleet-service clears all scenarios (use Export JSON to keep one).
* **Per-service models**: services share a JSON contract, not Python code, so they can be deployed independently.
