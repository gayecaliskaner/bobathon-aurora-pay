from decimal import Decimal
import re

from pydantic import BaseModel, Field, model_validator, field_validator


class AccountCreate(BaseModel):
    id: str
    owner_name: str
    iban: str
    balance: Decimal = Field(ge=0, decimal_places=2)
    currency: str = "TRY"


class TransferRequest(BaseModel):
    from_account: str
    to_account: str
    amount: Decimal = Field(gt=0, decimal_places=2)
    currency: str = "TRY"
    note: str | None = None

    @model_validator(mode="after")
    def _accounts_differ(self):
        if self.from_account == self.to_account:
            raise ValueError("Gönderen ve alıcı hesap aynı olamaz")
        return self


class ArchiveRequest(BaseModel):
    filename: str

    @field_validator("filename")
    @classmethod
    def validate_filename(cls, v: str) -> str:
        if not re.match(r"^[a-zA-Z0-9_-]+$", v):
            raise ValueError("Geçersiz dosya adı")
        return v
