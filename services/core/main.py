"""Aurora Core: account and transfer API."""

import logging

from fastapi import FastAPI, Header, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import reports, service, store
from .errors import AppError, TransferNotFound
from .models import AccountCreate, ArchiveRequest, TransferRequest

logger = logging.getLogger("aurora.core")

app = FastAPI(title="Aurora Core", version="0.1.0")


def _envelope(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"error": {"code": code, "message": message}})


@app.exception_handler(AppError)
async def _app_error_handler(request: Request, exc: AppError):
    return _envelope(exc.status_code, exc.code, exc.message)


@app.exception_handler(RequestValidationError)
async def _validation_error_handler(request: Request, exc: RequestValidationError):
    # Only field path and rule message are returned; submitted values are never echoed.
    details = "; ".join(
        f"{'.'.join(str(part) for part in err['loc'][1:]) or 'body'}: {err['msg']}" for err in exc.errors()
    )
    return _envelope(422, "VALIDATION_ERROR", f"Geçersiz istek: {details}")


@app.exception_handler(StarletteHTTPException)
async def _http_error_handler(request: Request, exc: StarletteHTTPException):
    return _envelope(exc.status_code, "HTTP_ERROR", "İstek işlenemedi")


@app.exception_handler(Exception)
async def _unexpected_error_handler(request: Request, exc: Exception):
    logger.error("Unexpected error", exc_info=exc)
    return _envelope(500, "INTERNAL_ERROR", "Beklenmeyen bir hata oluştu")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/accounts", status_code=201)
def create_account(data: AccountCreate):
    return service.create_account(data)


@app.get("/accounts/{account_id}")
def get_account(account_id: str):
    return service.get_account(account_id)


@app.post("/transfers", status_code=201)
def create_transfer(req: TransferRequest, idempotency_key: str | None = Header(default=None)):
    return service.execute_transfer(req, idempotency_key)


@app.get("/transfers/{transfer_id}")
def get_transfer(transfer_id: str):
    transfer = store.transfers.get(transfer_id)
    if transfer is None:
        raise TransferNotFound(transfer_id)
    return transfer


@app.get("/reports/transfers")
def transfers_by_owner(owner: str):
    return reports.find_transfers_by_owner(owner)


@app.post("/reports/archive")
def archive(req: ArchiveRequest):
    return {"exit_code": reports.archive_statements(req.filename)}
