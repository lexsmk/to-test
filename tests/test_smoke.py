import os
import uuid
import pytest
from dotenv import load_dotenv
from typing import Any
from src.client import Client, assert_keys, MEASUREMENT_KEYS, STRICT
from hypothesis import given, strategies as st

load_dotenv()

SMOKE_WEIGHT = float(os.getenv("SMOKE_WEIGHT", "12.5"))
SMOKE_DIRT = float(os.getenv("SMOKE_DIRT", "0.1"))


@pytest.mark.behavior
def test_happy_flow(barrel_factory, client: Client) -> None:
    barrel = barrel_factory()
    barrel_id = barrel["id"]
    all_barrels = client.barrels()
    assert any(b.get("id") == barrel_id for b in all_barrels)
    measurement = client.measurement_create({"barrelId": barrel_id, "dirtLevel": SMOKE_DIRT, "weight": SMOKE_WEIGHT})
    all_measurements = client.measurements()
    assert any(m.get("id") == measurement["id"] for m in all_measurements)
    detail = client.barrel(barrel_id)
    assert detail["id"] == barrel_id


@pytest.mark.robustness
def test_negative_nonexistent_barrel(client: Client) -> None:
    response = client._send("GET", f"/barrels/{uuid.uuid4()}")
    assert response.status_code in (400, 404)


@pytest.mark.behavior
def test_delete_barrel_removes_it(client: Client, barrel_factory) -> None:
    barrel_id = barrel_factory()["id"]
    status = client.barrel_delete(barrel_id)
    assert status in (200, 204, 202)
    response = client._send("GET", f"/barrels/{barrel_id}")
    if response.status_code == 500:
        pytest.fail("500 after delete (should be 400/404)")
    assert response.status_code in (400, 404)


@pytest.mark.contract
def test_measurement_detail(barrel_factory, client: Client) -> None:
    barrel = barrel_factory()
    measurement = client.measurement_create({"barrelId": barrel["id"], "dirtLevel": SMOKE_DIRT, "weight": SMOKE_WEIGHT})
    detail = client.measurement(measurement["id"])
    assert detail["id"] == measurement["id"]
    assert detail["barrelId"] == barrel["id"]
    assert_keys(detail, MEASUREMENT_KEYS)


@pytest.mark.parametrize(
    "payload, case",
    [
        ({"rfid": "r", "nfc": "n"}, "chybí qr"),
        ({"qr": "q", "nfc": "n"}, "chybí rfid"),
        ({"qr": "q", "rfid": "r"}, "chybí nfc"),
        ({"qr": "q", "rfid": "r", "nfc": "n", "extra": "x"}, "extra pole"),
    ],
)
@pytest.mark.contract
def test_barrel_invalid_payloads(client: Client, payload: dict[str, Any], case: str):
    response = client._send("POST", "/barrels", json=payload)
    if response.status_code in (200, 201):
        pytest.fail(f"accepted invalid barrel payload ({case}) -> {response.status_code}")
    assert response.status_code in (400, 422)


@pytest.mark.parametrize(
    "builder, case",
    [
        (lambda _, barrel_id: {"dirtLevel": SMOKE_DIRT, "weight": SMOKE_WEIGHT}, "chybí barrelId"),
        (lambda _, barrel_id: {"barrelId": barrel_id, "weight": SMOKE_WEIGHT}, "chybí dirtLevel"),
        (lambda _, barrel_id: {"barrelId": barrel_id, "dirtLevel": SMOKE_DIRT}, "chybí weight"),
        (lambda _, barrel_id: {"barrelId": "not-a-uuid", "dirtLevel": SMOKE_DIRT, "weight": SMOKE_WEIGHT}, "neplatné barrelId uuid"),
        (lambda _, barrel_id: {"barrelId": barrel_id, "dirtLevel": SMOKE_DIRT, "weight": SMOKE_WEIGHT, "extra": 1}, "extra pole"),
    ],
)
@pytest.mark.contract
def test_measurement_invalid_payloads(barrel_factory, client: Client, builder, case: str):
    barrel_id = barrel_factory()["id"]
    payload = builder({}, barrel_id)
    response = client._send("POST", "/measurements", json=payload)
    if response.status_code in (200, 201):
        pytest.fail(f"accepted invalid measurement payload ({case}) -> {response.status_code}")
    assert response.status_code in (400, 422)


@pytest.mark.contract
def test_barrel_additional_property_rejected(client: Client):
    response = client._send("POST", "/barrels", json={"qr": "q", "rfid": "r", "nfc": "n", "__hack": "1"})
    if response.status_code in (200, 201):
        pytest.fail(f"accepted barrel with unexpected property -> {response.status_code}")
    assert response.status_code in (400, 422)


_emptyish = st.one_of(
    st.just(""),
    st.text(alphabet=st.sampled_from([" ", "\t"]), min_size=1, max_size=32),
)

@pytest.mark.robustness
@given(qr=_emptyish)
def test_barrel_rejects_emptyish_qr(qr: str, client: Client):
    payload = {"qr": qr, "rfid": "r", "nfc": "n"}
    r = client._send("POST", "/barrels", json=payload)
    if r.status_code == 201:
        pytest.fail("accepted empty-ish qr")
    assert r.status_code in (400, 422)
