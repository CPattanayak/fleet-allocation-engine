import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from app import generator  # noqa: E402
from app.main import app  # noqa: E402
from app.models import GenerateRequest, Tightness  # noqa: E402


def test_generator_is_deterministic():
    a = generator.generate(GenerateRequest(seed=1), 1)
    b = generator.generate(GenerateRequest(seed=1), 1)
    assert [t.model_dump() for t in a[2]] == [t.model_dump() for t in b[2]]
    assert [o.model_dump() for o in a[3]] == [o.model_dump() for o in b[3]]


def test_generator_respects_sizes_and_windows():
    _, depots, trucks, orders = generator.generate(
        GenerateRequest(num_trucks=7, num_orders=33, tightness=Tightness.TIGHT), 5)
    assert len(depots) == 3 and len(trucks) == 7 and len(orders) == 33
    assert all(o.window_end - o.window_start <= 120 for o in orders)
    assert len({o.id for o in orders}) == 33


def test_crud_flow():
    with TestClient(app) as client:
        assert client.get("/health").json()["status"] == "ok"

        sc = client.post("/scenarios/generate", json={"num_trucks": 3, "num_orders": 5, "seed": 9}).json()
        sid = sc["id"]
        assert len(sc["trucks"]) == 3

        t = client.post(f"/scenarios/{sid}/trucks",
                        json={"depot": {"lat": 12.9, "lng": 77.6}, "capacity_kg": 400}).json()
        assert t["id"] == "T004"
        assert client.patch(f"/scenarios/{sid}/trucks/T004", json={"available": False}).json()["available"] is False

        new = client.post(f"/scenarios/{sid}/orders/random?count=4&seed=1").json()
        assert [o["id"] for o in new] == ["O006", "O007", "O008", "O009"]
        assert client.delete(f"/scenarios/{sid}/orders/O006").status_code == 204
        assert client.delete(f"/scenarios/{sid}/orders/O006").status_code == 404

        dup = client.post(f"/scenarios/{sid}/trucks",
                          json={"id": "T001", "depot": {"lat": 12.9, "lng": 77.6}, "capacity_kg": 1})
        assert dup.status_code == 409

        full = client.get(f"/scenarios/{sid}").json()
        assert len(full["trucks"]) == 4 and len(full["orders"]) == 8
        assert client.delete(f"/scenarios/{sid}").status_code == 204
        assert client.get(f"/scenarios/{sid}").status_code == 404


def test_unknown_city():
    with TestClient(app) as client:
        assert client.post("/scenarios/generate", json={"city": "atlantis"}).status_code == 422


def test_create_empty_scenario_then_build_it_up():
    with TestClient(app) as client:
        sc = client.post("/scenarios", json={"name": "My day", "city": "pune"}).json()
        sid = sc["id"]
        assert sc["trucks"] == [] and sc["orders"] == [] and sc["seed"] is None
        assert sc["city"]["id"] == "pune"

        t = client.post(f"/scenarios/{sid}/trucks",
                        json={"depot": {"lat": 18.52, "lng": 73.85}, "capacity_kg": 500}).json()
        assert t["id"] == "T001" and t["name"] == "Truck T001"
        o = client.post(f"/scenarios/{sid}/orders",
                        json={"location": {"lat": 18.53, "lng": 73.86}, "weight_kg": 20,
                              "window_start": 600, "window_end": 720}).json()
        assert o["id"] == "O001"

        # edit both
        t2 = client.put(f"/scenarios/{sid}/trucks/T001",
                        json={"depot": {"lat": 18.5, "lng": 73.8}, "capacity_kg": 900,
                              "capabilities": ["refrigerated"]}).json()
        assert t2["id"] == "T001" and t2["capacity_kg"] == 900 and t2["name"] == "Truck T001"
        o2 = client.put(f"/scenarios/{sid}/orders/O001",
                        json={"location": {"lat": 18.53, "lng": 73.86}, "weight_kg": 55,
                              "window_start": 600, "window_end": 660, "priority": 3}).json()
        assert o2["weight_kg"] == 55 and o2["priority"] == 3
        assert client.put(f"/scenarios/{sid}/orders/NOPE",
                          json={"location": {"lat": 1, "lng": 1}, "weight_kg": 1,
                                "window_start": 1, "window_end": 2}).status_code == 404


def test_import_scenario_with_data_and_validation():
    with TestClient(app) as client:
        body = {"name": "Imported", "trucks": [
            {"depot": {"lat": 12.9, "lng": 77.6}, "capacity_kg": 300},
            {"id": "BIG", "depot": {"lat": 12.95, "lng": 77.6}, "capacity_kg": 900}],
            "orders": [{"location": {"lat": 12.91, "lng": 77.61}, "weight_kg": 10,
                        "window_start": 540, "window_end": 600}]}
        sc = client.post("/scenarios", json=body).json()
        assert [t["id"] for t in sc["trucks"]] == ["T001", "BIG"]
        assert sc["orders"][0]["id"] == "O001"

        bad = client.post("/scenarios", json={"name": "x", "orders": [
            {"location": {"lat": 1, "lng": 1}, "weight_kg": 1, "window_start": 600, "window_end": 500}]})
        assert bad.status_code == 422
        assert client.post("/scenarios", json={"name": "x", "city": "atlantis"}).status_code == 422
        dup = client.post("/scenarios", json={"name": "x", "trucks": [
            {"id": "A", "depot": {"lat": 1, "lng": 1}, "capacity_kg": 1},
            {"id": "A", "depot": {"lat": 1, "lng": 1}, "capacity_kg": 1}]})
        assert dup.status_code == 422 and "duplicate" in dup.json()["detail"]


def test_demo_seed_is_optional():
    from app.main import seed_demo_scenarios
    from app.store import ScenarioStore
    s = ScenarioStore()
    seed_demo_scenarios(s)
    assert len(s.list()) == 2
