"""Aurora Limits & Statements servisi (bellek içi, v1).

Kaynak: docs/PRD-limits.md ve docs/API-SPEC-limits.yaml.
"""

from __future__ import annotations

import logging
import re
import threading
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from fastapi import Body, FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("aurora.limits")

CENT = Decimal("0.01")
DEFAULT_DAILY = Decimal("10000.00")
DEFAULT_PER_TRANSFER = Decimal("5000.00")
MAX_DESCRIPTION_LENGTH = 255

_CUSTOMER_ID_RE = re.compile(r"C[0-9]{6}")
_MONEY_RE = re.compile(r"[0-9]{1,15}(\.[0-9]{1,2})?")
_DATE_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")

REASON_PER_TRANSFER = "PER_TRANSFER_LIMIT_EXCEEDED"
REASON_DAILY = "DAILY_LIMIT_EXCEEDED"


class ValidationFailure(Exception):
    """Geçersiz girdi: 422 + VALIDATION_ERROR zarfı."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class _State:
    """Bellek içi depo. Karar + yazma tek kilit altında yapılır."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.limits: dict[str, tuple[Decimal, Decimal]] = {}
        self.usage: dict[tuple[str, date], Decimal] = {}
        self.entries: dict[str, list[tuple[date, Decimal, str | None]]] = {}


_state = _State()

app = FastAPI(title="Aurora Limits & Statements", version="1.0.0")


# ---- Hata zarfı -------------------------------------------------------------


def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


@app.exception_handler(ValidationFailure)
async def _on_validation_failure(_: Request, exc: ValidationFailure) -> JSONResponse:
    return _error(422, "VALIDATION_ERROR", exc.message)


@app.exception_handler(RequestValidationError)
async def _on_request_validation(_: Request, __: RequestValidationError) -> JSONResponse:
    return _error(422, "VALIDATION_ERROR", "İstek geçersiz: eksik veya hatalı alan")


@app.exception_handler(StarletteHTTPException)
async def _on_http_exception(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    if exc.status_code == 404:
        return _error(404, "NOT_FOUND", "Kaynak bulunamadı")
    if exc.status_code == 405:
        return _error(405, "METHOD_NOT_ALLOWED", "Bu yöntem desteklenmiyor")
    return _error(exc.status_code, "HTTP_ERROR", "İstek işlenemedi")


@app.exception_handler(Exception)
async def _on_unexpected(_: Request, exc: Exception) -> JSONResponse:
    logger.error("Unexpected error: %s", type(exc).__name__, exc_info=True)
    return _error(500, "INTERNAL_ERROR", "Beklenmeyen bir hata oluştu")


# ---- Doğrulama / biçim ------------------------------------------------------


def _check_customer_id(customer_id: str) -> str:
    if not _CUSTOMER_ID_RE.fullmatch(customer_id):
        raise ValidationFailure("customer_id 'C' + 6 rakam olmalı (örn. C004217)")
    return customer_id


def _parse_money(value: Any, field: str) -> Decimal:
    if not isinstance(value, str) or not _MONEY_RE.fullmatch(value):
        raise ValidationFailure(f"{field} en fazla 2 ondalıklı pozitif bir tutar (string) olmalı")
    amount = Decimal(value)
    if amount <= 0:
        raise ValidationFailure(f"{field} sıfırdan büyük olmalı")
    return amount.quantize(CENT, rounding=ROUND_HALF_UP)


def _parse_date(value: Any, field: str) -> date:
    if not isinstance(value, str) or not _DATE_RE.fullmatch(value):
        raise ValidationFailure(f"{field} YYYY-MM-DD biçiminde geçerli bir tarih olmalı")
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ValidationFailure(f"{field} YYYY-MM-DD biçiminde geçerli bir tarih olmalı") from None


def _require_object(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValidationFailure("İstek gövdesi bir JSON nesnesi olmalı")
    return payload


def _money(amount: Decimal) -> str:
    return f"{amount.quantize(CENT, rounding=ROUND_HALF_UP):.2f}"


def _limits_for(customer_id: str) -> tuple[Decimal, Decimal, str]:
    custom = _state.limits.get(customer_id)
    if custom is None:
        return DEFAULT_DAILY, DEFAULT_PER_TRANSFER, "default"
    return custom[0], custom[1], "custom"


def _limits_body(customer_id: str) -> dict[str, str]:
    daily, per_transfer, source = _limits_for(customer_id)
    return {
        "customer_id": customer_id,
        "daily_limit": _money(daily),
        "per_transfer_limit": _money(per_transfer),
        "source": source,
    }


# ---- Uç noktalar ------------------------------------------------------------


@app.put("/limits/{customer_id}")
def put_limits(customer_id: str, payload: Any = Body(default=None)) -> dict[str, str]:
    _check_customer_id(customer_id)
    body = _require_object(payload)
    daily = _parse_money(body.get("daily_limit"), "daily_limit")
    per_transfer = _parse_money(body.get("per_transfer_limit"), "per_transfer_limit")
    if per_transfer > daily:
        raise ValidationFailure("per_transfer_limit, daily_limit değerinden büyük olamaz")
    with _state.lock:
        _state.limits[customer_id] = (daily, per_transfer)
        result = _limits_body(customer_id)
    logger.info("Limits updated customer_id=%s", customer_id)
    return result


@app.get("/limits/{customer_id}")
def get_limits(customer_id: str) -> dict[str, str]:
    _check_customer_id(customer_id)
    with _state.lock:
        return _limits_body(customer_id)


@app.post("/limits/{customer_id}/authorize")
def authorize(customer_id: str, payload: Any = Body(default=None)) -> dict[str, Any]:
    _check_customer_id(customer_id)
    body = _require_object(payload)
    amount = _parse_money(body.get("amount"), "amount")
    occurred_on = _parse_date(body.get("occurred_on"), "occurred_on")
    description = body.get("description")
    if description is not None and (not isinstance(description, str) or len(description) > MAX_DESCRIPTION_LENGTH):
        raise ValidationFailure(f"description en fazla {MAX_DESCRIPTION_LENGTH} karakterlik bir metin olmalı")

    with _state.lock:
        daily, per_transfer, _source = _limits_for(customer_id)
        used = _state.usage.get((customer_id, occurred_on), Decimal("0.00"))
        reason: str | None = None
        if amount > per_transfer:
            reason = REASON_PER_TRANSFER
        elif used + amount > daily:
            reason = REASON_DAILY
        if reason is None:
            used += amount
            _state.usage[(customer_id, occurred_on)] = used
            _state.entries.setdefault(customer_id, []).append((occurred_on, amount, description))
        remaining = max(daily - used, Decimal("0.00"))

    logger.info("Authorization decided customer_id=%s allowed=%s", customer_id, reason is None)
    return {
        "customer_id": customer_id,
        "allowed": reason is None,
        "reason": reason,
        "remaining_daily": _money(remaining),
    }


@app.get("/statements/{customer_id}")
def get_statement(
    customer_id: str,
    from_: str | None = Query(default=None, alias="from"),
    to: str | None = Query(default=None),
) -> dict[str, Any]:
    _check_customer_id(customer_id)
    start = _parse_date(from_, "from")
    end = _parse_date(to, "to")
    if start > end:
        raise ValidationFailure("from, to tarihinden sonra olamaz")

    with _state.lock:
        approved = list(_state.entries.get(customer_id, []))
    selected = sorted((e for e in approved if start <= e[0] <= end), key=lambda e: e[0])
    total = sum((e[1] for e in selected), Decimal("0.00"))
    return {
        "customer_id": customer_id,
        "from": start.isoformat(),
        "to": end.isoformat(),
        "entries": [
            {"occurred_on": d.isoformat(), "amount": _money(a), "description": desc} for d, a, desc in selected
        ],
        "total": _money(total),
    }
