# Aurora Pay Standards (source: docs/ENGINEERING-HANDBOOK.md)

When writing test expectations, assert against these standards. If the handbook and this file ever differ, the handbook wins.

## 1. Money

1. Amounts are held as `decimal.Decimal`. No `float` arithmetic on money.
2. Rounding is `ROUND_HALF_UP`, 2 decimals.
3. Responses may carry amounts as JSON numbers or strings, but the value must be exact to the cent (`99.00`, never `99.00000000000006`).
4. Fee rules: single source is `docs/FEE-POLICY.md`.

## 2. Error handling

All errors return a single envelope. A bare `{"detail": ...}`, a stack trace, or an internal message must never reach the client.

```json
{"error": {"code": "ACCOUNT_NOT_FOUND", "message": "Hesap bulunamadi: ACC-9999"}}
```

| Situation | HTTP | `code` |
|---|---|---|
| Invalid input (missing field, amount <= 0, negative balance, type error) | 422 | `VALIDATION_ERROR` |
| Sender and receiver are the same account | 422 | `VALIDATION_ERROR` |
| Account not found | 404 | `ACCOUNT_NOT_FOUND` |
| Account already exists (second record with same `id`) | 409 | `ACCOUNT_ALREADY_EXISTS` |
| Transfer not found | 404 | `TRANSFER_NOT_FOUND` |
| Insufficient funds | 409 | `INSUFFICIENT_FUNDS` |
| Unexpected error | 500 | `INTERNAL_ERROR` (fixed message: "Beklenmeyen bir hata olustu") |

Additional rules:

- Money movement is atomic: if any step fails, no balance has changed. Validate first, then write.
- Money-moving endpoints support the `Idempotency-Key` header. A second request with the same key creates no new transaction and returns the first response.
- Unexpected errors are logged server-side in detail; the client receives `INTERNAL_ERROR`.

## 3. Logging

- No PII in logs: full name, IBAN, national ID (TCKN), phone, e-mail, card number.
- Log lines use only technical identifiers: `account_id`, `transfer_id`.
- Messages are written with the `logging` module. `print` is not used.

## 4. Security

- Secrets (API key, password, JWT secret) are not in code or the repo; they come from environment variables. Tests must not embed real secrets.
- SQL is always parameterized; user input is never concatenated into SQL.
- No shell command is run with user input. File names are validated and path traversal (`..`) is not allowed.
- Docker images run as a non-root user; no `ADD <url>`; no secrets baked into the image.
- No exposed (`0.0.0.0/0`) rules, public buckets, or unencrypted storage in infrastructure code.
- Dependencies are not kept on known vulnerable versions.
