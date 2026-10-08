from fastapi.testclient import TestClient

from app.main import app

from .conftest import random_scenario

client = TestClient(app)


def payload(algorithm="greedy"):
    trucks, orders = random_scenario(3, n_trucks=4, n_orders=12)
    return {"trucks": [t.model_dump(mode="json") for t in trucks],
            "orders": [o.model_dump(mode="json") for o in orders],
            "algorithm": algorithm}


def test_health():
    assert client.get("/health").json()["status"] == "ok"


def test_algorithms_listed():
    ids = {a["id"] for a in client.get("/algorithms").json()}
    assert ids == {"greedy", "hungarian"}


def test_allocate():
    r = client.post("/allocate", json=payload("hungarian"))
    assert r.status_code == 200
    body = r.json()
    assert body["algorithm"] == "hungarian"
    assert body["metrics"]["total_orders"] == 12


def test_compare_returns_both():
    r = client.post("/compare", json=payload())
    assert set(r.json()) == {"greedy", "hungarian"}


def test_invalid_window_rejected():
    p = payload()
    p["orders"][0]["window_end"] = p["orders"][0]["window_start"] - 1
    assert client.post("/allocate", json=p).status_code == 422


def test_duplicate_ids_rejected():
    p = payload()
    p["trucks"][1]["id"] = p["trucks"][0]["id"]
    r = client.post("/allocate", json=p)
    assert r.status_code == 422 and "duplicate" in r.json()["detail"]
