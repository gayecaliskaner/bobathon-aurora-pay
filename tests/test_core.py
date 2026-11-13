import logging
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from services.core import store
from services.core.main import app

client = TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def _reset_store():
    store.reset()


def _account(account_id, balance="1000.00", owner="Ayse Yilmaz", iban="TR000000000000000000000001"):
    return {"id": account_id, "owner_name": owner, "iban": iban, "balance": balance}


def _create(account_id, balance="1000.00", **kwargs):
    response = client.post("/accounts", json=_account(account_id, balance, **kwargs))
    assert response.status_code == 201
    return response


def _transfer(src, dst, amount, headers=None):
    return client.post(
        "/transfers",
        json={"from_account": src, "to_account": dst, "amount": amount},
        headers=headers,
    )


def _balance(account_id):
    return Decimal(str(client.get(f"/accounts/{account_id}").json()["balance"]))


def _assert_envelope(response, status, code):
    body = response.json()
    assert response.status_code == status
    assert "detail" not in body
    assert set(body.keys()) == {"error"}
    assert body["error"]["code"] == code
    assert isinstance(body["error"]["message"], str) and body["error"]["message"]


# --- Accounts -------------------------------------------------------------


def test_create_account_returns_201_with_account_data():
    # Arrange
    payload = _account("ACC-1", "250.50")

    # Act
    response = client.post("/accounts", json=payload)

    # Assert
    assert response.status_code == 201
    body = response.json()
    assert body["id"] == "ACC-1"
    assert body["owner_name"] == "Ayse Yilmaz"
    assert Decimal(str(body["balance"])) == Decimal("250.50")
    assert body["currency"] == "TRY"


def test_get_account_returns_created_account():
    # Arrange
    _create("ACC-1", "10.00")

    # Act
    response = client.get("/accounts/ACC-1")

    # Assert
    assert response.status_code == 200
    assert response.json()["id"] == "ACC-1"
    assert Decimal(str(response.json()["balance"])) == Decimal("10.00")


def test_get_account_returns_not_found_for_unknown_id():
    # Arrange: empty store

    # Act
    response = client.get("/accounts/ACC-9999")

    # Assert
    _assert_envelope(response, 404, "ACCOUNT_NOT_FOUND")
    assert "ACC-9999" in response.json()["error"]["message"]


def test_create_account_returns_conflict_when_id_exists():
    # Arrange
    _create("ACC-1", "10.00")

    # Act
    response = client.post("/accounts", json=_account("ACC-1", "99.00"))

    # Assert
    _assert_envelope(response, 409, "ACCOUNT_ALREADY_EXISTS")
    assert _balance("ACC-1") == Decimal("10.00")


def test_create_account_accepts_zero_balance_at_boundary():
    # Arrange
    payload = _account("ACC-0", "0.00")

    # Act
    response = client.post("/accounts", json=payload)

    # Assert
    assert response.status_code == 201
    assert Decimal(str(response.json()["balance"])) == Decimal("0.00")


def test_create_account_rejects_negative_balance():
    # Arrange
    payload = _account("ACC-1", "-0.01")

    # Act
    response = client.post("/accounts", json=payload)

    # Assert
    _assert_envelope(response, 422, "VALIDATION_ERROR")
    assert client.get("/accounts/ACC-1").status_code == 404


def test_create_account_rejects_missing_field():
    # Arrange
    payload = {"id": "ACC-1", "owner_name": "Ayse Yilmaz", "iban": "TR000000000000000000000001"}

    # Act
    response = client.post("/accounts", json=payload)

    # Assert
    _assert_envelope(response, 422, "VALIDATION_ERROR")


def test_create_account_rejects_balance_with_three_decimals():
    # Arrange
    payload = _account("ACC-1", "10.001")

    # Act
    response = client.post("/accounts", json=payload)

    # Assert
    _assert_envelope(response, 422, "VALIDATION_ERROR")


def test_create_account_rejects_wrong_type_without_echoing_value():
    # Arrange
    payload = _account("ACC-1", "not-a-number")

    # Act
    response = client.post("/accounts", json=payload)

    # Assert
    _assert_envelope(response, 422, "VALIDATION_ERROR")
    assert "not-a-number" not in response.text


# --- Transfers: fee policy (docs/FEE-POLICY.md) ----------------------------


@pytest.mark.parametrize(
    ("amount", "expected_fee"),
    [
        ("0.01", "0.00"),  # lower boundary: 0.00005 rounds to 0.00
        ("3.00", "0.02"),  # 0.015 rounds half up
        ("10.10", "0.05"),  # 0.0505 -> 0.05
        ("100.00", "0.50"),
        ("999.99", "5.00"),  # just below threshold, 0.50% rate
        ("1000.00", "2.50"),  # threshold inclusive, 0.25% rate
        ("1234.56", "3.09"),  # 3.0864 -> 3.09
    ],
)
def test_transfer_fee_matches_policy_for_amount(amount, expected_fee):
    # Arrange
    _create("ACC-1", "5000.00")
    _create("ACC-2", "0.00")

    # Act
    response = _transfer("ACC-1", "ACC-2", amount)

    # Assert
    assert response.status_code == 201
    body = response.json()
    assert Decimal(str(body["fee"])) == Decimal(expected_fee)
    assert Decimal(str(body["amount"])) == Decimal(amount)
    assert _balance("ACC-1") == Decimal("5000.00") - Decimal(amount) - Decimal(expected_fee)
    assert _balance("ACC-2") == Decimal(amount)


def test_transfer_fee_is_exact_to_the_cent_in_response():
    # Arrange
    _create("ACC-1", "5000.00")
    _create("ACC-2", "0.00")

    # Act
    response = _transfer("ACC-1", "ACC-2", "999.99")

    # Assert
    fee = Decimal(str(response.json()["fee"]))
    assert fee == fee.quantize(Decimal("0.01"))
    assert "00000" not in str(response.json()["fee"])


# --- Transfers: happy path & retrieval ------------------------------------


def test_transfer_completes_and_moves_money_with_fee():
    # Arrange
    _create("ACC-1", "1000.00")
    _create("ACC-2", "50.00")

    # Act
    response = _transfer("ACC-1", "ACC-2", "100.00")

    # Assert
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "COMPLETED"
    assert body["from_account"] == "ACC-1"
    assert body["to_account"] == "ACC-2"
    assert body["currency"] == "TRY"
    assert body["id"]
    assert _balance("ACC-1") == Decimal("899.50")
    assert _balance("ACC-2") == Decimal("150.00")


def test_get_transfer_returns_created_transfer():
    # Arrange
    _create("ACC-1")
    _create("ACC-2", "0.00")
    transfer_id = _transfer("ACC-1", "ACC-2", "10.00").json()["id"]

    # Act
    response = client.get(f"/transfers/{transfer_id}")

    # Assert
    assert response.status_code == 200
    assert response.json()["id"] == transfer_id
    assert Decimal(str(response.json()["amount"])) == Decimal("10.00")


def test_get_transfer_returns_not_found_for_unknown_id():
    # Arrange: empty store

    # Act
    response = client.get("/transfers/does-not-exist")

    # Assert
    _assert_envelope(response, 404, "TRANSFER_NOT_FOUND")


# --- Transfers: negative cases & atomicity ---------------------------------


def test_transfer_rejects_insufficient_funds_and_keeps_balances():
    # Arrange
    _create("ACC-1", "50.00")
    _create("ACC-2", "10.00")

    # Act
    response = _transfer("ACC-1", "ACC-2", "50.00")  # needs 50.25 with fee

    # Assert
    _assert_envelope(response, 409, "INSUFFICIENT_FUNDS")
    assert _balance("ACC-1") == Decimal("50.00")
    assert _balance("ACC-2") == Decimal("10.00")
    assert store.transfers == {}


def test_transfer_succeeds_when_balance_equals_amount_plus_fee_exactly():
    # Arrange
    _create("ACC-1", "100.50")  # 100.00 + 0.50 fee
    _create("ACC-2", "0.00")

    # Act
    response = _transfer("ACC-1", "ACC-2", "100.00")

    # Assert
    assert response.status_code == 201
    assert _balance("ACC-1") == Decimal("0.00")
    assert _balance("ACC-2") == Decimal("100.00")


def test_transfer_rejects_when_balance_is_one_cent_short_of_amount_plus_fee():
    # Arrange
    _create("ACC-1", "100.49")
    _create("ACC-2", "0.00")

    # Act
    response = _transfer("ACC-1", "ACC-2", "100.00")

    # Assert
    _assert_envelope(response, 409, "INSUFFICIENT_FUNDS")
    assert _balance("ACC-1") == Decimal("100.49")


def test_transfer_rejects_unknown_destination_and_keeps_sender_balance():
    # Arrange
    _create("ACC-1", "500.00")

    # Act
    response = _transfer("ACC-1", "ACC-404", "10.00")

    # Assert
    _assert_envelope(response, 404, "ACCOUNT_NOT_FOUND")
    assert _balance("ACC-1") == Decimal("500.00")
    assert store.transfers == {}


def test_transfer_rejects_unknown_source_account():
    # Arrange
    _create("ACC-2", "0.00")

    # Act
    response = _transfer("ACC-404", "ACC-2", "10.00")

    # Assert
    _assert_envelope(response, 404, "ACCOUNT_NOT_FOUND")
    assert _balance("ACC-2") == Decimal("0.00")


def test_transfer_rejects_same_source_and_destination():
    # Arrange
    _create("ACC-1", "500.00")

    # Act
    response = _transfer("ACC-1", "ACC-1", "10.00")

    # Assert
    _assert_envelope(response, 422, "VALIDATION_ERROR")
    assert _balance("ACC-1") == Decimal("500.00")


def test_transfer_rejects_zero_amount_at_boundary():
    # Arrange
    _create("ACC-1")
    _create("ACC-2", "0.00")

    # Act
    response = _transfer("ACC-1", "ACC-2", "0.00")

    # Assert
    _assert_envelope(response, 422, "VALIDATION_ERROR")
    assert _balance("ACC-1") == Decimal("1000.00")


def test_transfer_rejects_negative_amount():
    # Arrange
    _create("ACC-1")
    _create("ACC-2", "0.00")

    # Act
    response = _transfer("ACC-1", "ACC-2", "-5.00")

    # Assert
    _assert_envelope(response, 422, "VALIDATION_ERROR")
    assert _balance("ACC-1") == Decimal("1000.00")
    assert _balance("ACC-2") == Decimal("0.00")


def test_transfer_rejects_amount_with_three_decimals():
    # Arrange
    _create("ACC-1")
    _create("ACC-2", "0.00")

    # Act
    response = _transfer("ACC-1", "ACC-2", "1.005")

    # Assert
    _assert_envelope(response, 422, "VALIDATION_ERROR")


def test_transfer_rejects_missing_amount():
    # Arrange
    _create("ACC-1")
    _create("ACC-2", "0.00")

    # Act
    response = client.post("/transfers", json={"from_account": "ACC-1", "to_account": "ACC-2"})

    # Assert
    _assert_envelope(response, 422, "VALIDATION_ERROR")


# --- Transfers: idempotency -------------------------------------------------


def test_transfer_with_same_idempotency_key_returns_first_response_without_new_transaction():
    # Arrange
    _create("ACC-1", "1000.00")
    _create("ACC-2", "0.00")
    headers = {"Idempotency-Key": "key-1"}

    # Act
    first = _transfer("ACC-1", "ACC-2", "100.00", headers=headers)
    second = _transfer("ACC-1", "ACC-2", "100.00", headers=headers)

    # Assert
    assert first.status_code == 201
    assert second.json() == first.json()
    assert len(store.transfers) == 1
    assert _balance("ACC-1") == Decimal("899.50")
    assert _balance("ACC-2") == Decimal("100.00")


def test_transfer_with_different_idempotency_keys_creates_separate_transactions():
    # Arrange
    _create("ACC-1", "1000.00")
    _create("ACC-2", "0.00")

    # Act
    first = _transfer("ACC-1", "ACC-2", "100.00", headers={"Idempotency-Key": "key-1"})
    second = _transfer("ACC-1", "ACC-2", "100.00", headers={"Idempotency-Key": "key-2"})

    # Assert
    assert first.json()["id"] != second.json()["id"]
    assert len(store.transfers) == 2
    assert _balance("ACC-1") == Decimal("799.00")


def test_transfer_without_idempotency_key_creates_new_transaction_each_time():
    # Arrange
    _create("ACC-1", "1000.00")
    _create("ACC-2", "0.00")

    # Act
    first = _transfer("ACC-1", "ACC-2", "10.00")
    second = _transfer("ACC-1", "ACC-2", "10.00")

    # Assert
    assert first.json()["id"] != second.json()["id"]
    assert len(store.transfers) == 2


# --- Logging ---------------------------------------------------------------


def test_transfer_log_contains_technical_ids_and_no_pii(caplog):
    # Arrange
    _create("ACC-1", "1000.00", owner="Ayse Yilmaz", iban="TR111111111111111111111111")
    _create("ACC-2", "0.00")

    # Act
    with caplog.at_level(logging.INFO, logger="aurora.core"):
        response = _transfer("ACC-1", "ACC-2", "10.00")

    # Assert
    transfer_id = response.json()["id"]
    assert transfer_id in caplog.text
    assert "ACC-1" in caplog.text
    assert "Ayse" not in caplog.text
    assert "TR111111111111111111111111" not in caplog.text


# --- Reports ---------------------------------------------------------------


def test_transfers_by_owner_returns_matching_transfers():
    # Arrange
    _create("ACC-1", "1000.00", owner="Ayse Yilmaz")
    _create("ACC-2", "0.00", owner="Mehmet Kaya")
    transfer_id = _transfer("ACC-1", "ACC-2", "10.00").json()["id"]

    # Act
    response = client.get("/reports/transfers", params={"owner": "Ayse Yilmaz"})

    # Assert
    assert response.status_code == 200
    assert transfer_id in [row["id"] for row in response.json()]


def test_transfers_by_owner_returns_empty_list_for_unknown_owner():
    # Arrange: no transfers for this owner

    # Act
    response = client.get("/reports/transfers", params={"owner": "Nobody Atall"})

    # Assert
    assert response.status_code == 200
    assert response.json() == []


def test_transfers_by_owner_rejects_missing_owner_parameter():
    # Arrange / Act
    response = client.get("/reports/transfers")

    # Assert
    _assert_envelope(response, 422, "VALIDATION_ERROR")


# --- Generic error envelope --------------------------------------------------


def test_unknown_route_returns_envelope_without_detail():
    # Arrange / Act
    response = client.get("/no-such-route")

    # Assert
    assert response.status_code == 404
    assert "detail" not in response.json()
    assert set(response.json()["error"].keys()) == {"code", "message"}


def test_archive_rejects_missing_filename():
    # Arrange / Act
    response = client.post("/reports/archive", json={})

    # Assert
    _assert_envelope(response, 422, "VALIDATION_ERROR")
