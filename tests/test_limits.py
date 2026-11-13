import itertools

import pytest
from fastapi.testclient import TestClient

from services.limits.main import app

_ids = itertools.count(1)


@pytest.fixture(scope="module")
def client():
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def cid():
    # Servis bellek içi ve reset API'si yok: her test kendi müşterisini kullanır.
    return f"C{800000 + next(_ids):06d}"


def _authorize(client, cid, amount, day="2025-03-14", description=None):
    body = {"amount": amount, "occurred_on": day}
    if description is not None:
        body["description"] = description
    return client.post(f"/limits/{cid}/authorize", json=body)


def test_prd_example_scenario_matches_expected_decisions(client, cid):
    # Arrange
    client.put(f"/limits/{cid}", json={"daily_limit": "5000.00", "per_transfer_limit": "2000.00"})

    # Act
    steps = [
        _authorize(client, cid, "1500.00").json(),
        _authorize(client, cid, "2500.00").json(),
        _authorize(client, cid, "2000.00").json(),
        _authorize(client, cid, "1600.00").json(),
        _authorize(client, cid, "1600.00", day="2025-03-15").json(),
    ]

    # Assert
    assert [(s["allowed"], s["reason"], s["remaining_daily"]) for s in steps] == [
        (True, None, "3500.00"),
        (False, "PER_TRANSFER_LIMIT_EXCEEDED", "3500.00"),
        (True, None, "1500.00"),
        (False, "DAILY_LIMIT_EXCEEDED", "1500.00"),
        (True, None, "3400.00"),
    ]


def test_remaining_daily_is_clamped_when_limit_lowered_below_usage(client, cid):
    # Arrange
    client.put(f"/limits/{cid}", json={"daily_limit": "5000.00", "per_transfer_limit": "2000.00"})
    _authorize(client, cid, "2000.00")
    client.put(f"/limits/{cid}", json={"daily_limit": "1000.00", "per_transfer_limit": "500.00"})

    # Act
    body = _authorize(client, cid, "100.00").json()

    # Assert
    assert body["allowed"] is False and body["reason"] == "DAILY_LIMIT_EXCEEDED"
    assert body["remaining_daily"] == "0.00"


def test_description_too_long_returns_validation_error(client, cid):
    # Arrange / Act
    response = _authorize(client, cid, "10.00", description="x" * 256)

    # Assert
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_description_at_max_length_is_accepted(client, cid):
    # Arrange / Act
    response = _authorize(client, cid, "10.00", description="x" * 255)

    # Assert
    assert response.status_code == 200 and response.json()["allowed"] is True


def test_numeric_json_amount_is_rejected(client, cid):
    # Arrange / Act
    response = client.post(f"/limits/{cid}/authorize", json={"amount": 10.5, "occurred_on": "2025-03-14"})

    # Assert
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_non_object_body_returns_validation_error(client, cid):
    # Arrange / Act
    response = client.put(f"/limits/{cid}", json=["x"])

    # Assert
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_unknown_route_returns_not_found_envelope(client):
    # Arrange / Act
    response = client.get("/nope")

    # Assert
    assert response.status_code == 404
    assert response.json() == {"error": {"code": "NOT_FOUND", "message": "Kaynak bulunamadı"}}


def test_wrong_method_returns_method_not_allowed_envelope(client, cid):
    # Arrange / Act
    response = client.delete(f"/limits/{cid}")

    # Assert
    assert response.status_code == 405
    assert response.json()["error"]["code"] == "METHOD_NOT_ALLOWED"


def test_unexpected_error_returns_internal_error_envelope(client, cid, monkeypatch):
    # Arrange
    def boom(_customer_id):
        raise RuntimeError("secret internal detail")

    monkeypatch.setattr("services.limits.main._limits_body", boom)

    # Act
    response = client.get(f"/limits/{cid}")

    # Assert
    assert response.status_code == 500
    assert response.json() == {"error": {"code": "INTERNAL_ERROR", "message": "Beklenmeyen bir hata oluştu"}}
