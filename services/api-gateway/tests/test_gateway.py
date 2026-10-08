"""Gateway tests with mocked downstream services (httpx.MockTransport)."""
import sys
from pathlib import Path

import httpx
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import main  # noqa: E402

SCENARIO = {"id": "abc", "trucks": [{"id": "T1"}], "orders": [{"id": "O1"}]}


def metrics(dist, assigned):
    keys = list(main.LOWER_IS_BETTER | main.HIGHER_IS_BETTER)
    m = {k: 0.0 for k in keys}
    m.update(total_distance_km=dist, assigned_orders=assigned)
    return m


calls = []


def handler(request: httpx.Request) -> httpx.Response:
    calls.append((request.method, request.url.host, request.url.path))
    host, path = request.url.host, request.url.path
    if path == "/health":
        return httpx.Response(200, json={"status": "ok"})
    if host == "localhost" and request.url.port == 8001:
        if path == "/scenarios/abc":
            return httpx.Response(200, json=SCENARIO)
        if path == "/scenarios/missing":
            return httpx.Response(404, json={"detail": "scenario missing not found"})
        if path == "/scenarios":
            return httpx.Response(200, json=[{"id": "abc"}])
    if path == "/allocate":
        import json
        algo = json.loads(request.content)["algorithm"]
        dist = 100 if algo == "greedy" else 80
        return httpx.Response(200, json={"algorithm": algo, "metrics": metrics(dist, 1)})
    return httpx.Response(404, json={"detail": "nope"})


def client():
    main.app.state.fleet, main.app.state.alloc = main.make_clients(httpx.MockTransport(handler))
    return TestClient(main.app)


def test_health_aggregates():
    with client() as c:
        body = c.get("/api/health").json()
        assert body["status"] == "ok"
        assert body["services"] == {"fleet-service": "ok", "allocation-service": "ok"}


def test_compare_runs_both_and_summarises():
    with client() as c:
        body = c.post("/api/compare", json={"scenario_id": "abc"}).json()
        assert set(body["results"]) == {"greedy", "hungarian"}
        assert body["summary"]["total_distance_km"]["winner"] == "hungarian"
        assert body["summary"]["assigned_orders"]["winner"] == "tie"


def test_allocate_404_propagates():
    with client() as c:
        r = c.post("/api/allocate", json={"scenario_id": "missing"})
        assert r.status_code == 404 and "not found" in r.json()["detail"]


def test_scenario_proxy():
    with client() as c:
        assert c.get("/api/scenarios").json() == [{"id": "abc"}]
        assert c.get("/api/scenarios/abc").json()["id"] == "abc"


def test_upstream_down_gives_502():
    def boom(_):
        raise httpx.ConnectError("down")
    main.app.state.fleet, main.app.state.alloc = main.make_clients(httpx.MockTransport(boom))
    with TestClient(main.app) as c:
        assert c.post("/api/allocate", json={"scenario_id": "abc"}).status_code == 502
        assert c.get("/api/health").json()["status"] == "degraded"


def test_scenario_create_and_put_are_proxied():
    seen = []

    def h(request: httpx.Request) -> httpx.Response:
        seen.append((request.method, request.url.path))
        return httpx.Response(201 if request.method == "POST" else 200, json={"ok": True})

    main.app.state.fleet, main.app.state.alloc = main.make_clients(httpx.MockTransport(h))
    with TestClient(main.app) as c:
        assert c.post("/api/scenarios", json={"name": "x"}).status_code == 201
        assert c.put("/api/scenarios/abc/trucks/T1", json={}).status_code == 200
    assert ("POST", "/scenarios") in seen and ("PUT", "/scenarios/abc/trucks/T1") in seen
