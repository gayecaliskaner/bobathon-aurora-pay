"""Transfer business logic."""

import logging
import threading
import uuid
from datetime import datetime, timezone

from . import fees, reports, store
from .errors import AccountAlreadyExists, AccountNotFound, InsufficientFunds
from .models import AccountCreate, TransferRequest

logger = logging.getLogger("aurora.core")

# Serialises state changes so check-then-write sequences (idempotency lookup,
# duplicate account check, balance check + debit) are atomic across threads.
_lock = threading.Lock()


def get_account(account_id: str) -> dict:
    account = store.accounts.get(account_id)
    if account is None:
        raise AccountNotFound(account_id)
    return account


def create_account(data: AccountCreate) -> dict:
    with _lock:
        if data.id in store.accounts:
            raise AccountAlreadyExists(data.id)
        account = data.model_dump()
        store.accounts[data.id] = account
    return account


def execute_transfer(req: TransferRequest, idempotency_key: str | None = None) -> dict:
    with _lock:
        if idempotency_key is not None and idempotency_key in store.idempotency:
            return store.idempotency[idempotency_key]

        # Validate everything first, write afterwards: a failure must not change any balance.
        src = get_account(req.from_account)
        dst = get_account(req.to_account)
        fee = fees.fee_for(req.amount)
        total = req.amount + fee
        if src["balance"] < total:
            raise InsufficientFunds()

        transfer = {
            "id": str(uuid.uuid4()),
            "from_account": req.from_account,
            "to_account": req.to_account,
            "amount": req.amount,
            "fee": fee,
            "currency": req.currency,
            "status": "COMPLETED",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        reports.record_transfer(transfer, src["owner_name"])

        src["balance"] = src["balance"] - total
        dst["balance"] = dst["balance"] + req.amount
        store.transfers[transfer["id"]] = transfer
        if idempotency_key is not None:
            store.idempotency[idempotency_key] = transfer

    logger.info(
        "Transfer completed: transfer_id=%s from_account=%s to_account=%s",
        transfer["id"],
        transfer["from_account"],
        transfer["to_account"],
    )
    return transfer
