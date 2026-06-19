from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ERPConnectionError(Exception):
    """Raised when an ERP connection fails (auth, network, timeout)."""


class RFQParseError(Exception):
    """Raised when an RFQ document cannot be parsed into line items."""


class RFQLineItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    line_number: int = Field(ge=1)
    part_number: str = Field(min_length=1, max_length=100)
    quantity: int = Field(ge=1)
    required_date: date | None = None
    customer_notes: str | None = Field(default=None, max_length=500)
    manufacturer: str | None = Field(default=None, max_length=200)

    @field_validator("part_number")
    @classmethod
    def sanitize_part_number(cls, v: str) -> str:
        sanitized = v.strip()
        if not sanitized:
            raise ValueError("part_number cannot be empty after stripping whitespace")
        if any(ord(c) < 32 for c in sanitized if c not in ("\t",)):  # noqa: PLR2004
            raise ValueError("part_number contains invalid control characters")
        return sanitized


class ERPPartResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    part_number: str
    description: str
    unit_price: Decimal = Field(ge=Decimal("0"))
    available_qty: int = Field(ge=0)
    lead_time_days: int = Field(ge=0)
    manufacturer: str


class QuoteLineItem(BaseModel):
    rfq_line: RFQLineItem
    erp_result: ERPPartResult | None = None
    status: Literal["found", "not_found", "substituted"]
    unit_price: Decimal | None = None
    extended_price: Decimal | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def validate_prices_on_found(self) -> QuoteLineItem:
        if self.status in ("found", "substituted"):
            if self.unit_price is None:
                raise ValueError(
                    "unit_price required when status is 'found' or 'substituted'"
                )
            if self.extended_price is None:
                raise ValueError(
                    "extended_price required when status is 'found' or 'substituted'"
                )
        return self


class Quote(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    rfq_source: str
    lines: list[QuoteLineItem]
    total_price: Decimal
    currency: str = "USD"

    @model_validator(mode="after")
    def validate_total_matches_lines(self) -> Quote:
        computed = sum(
            (
                line.extended_price
                for line in self.lines
                if line.extended_price is not None
            ),
            Decimal("0"),
        )
        if abs(computed - self.total_price) > Decimal("0.01"):
            raise ValueError(
                f"total_price {self.total_price} does not match computed sum {computed}"
            )
        return self

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")

    def summary(self) -> str:
        counts: dict[str, int] = {"found": 0, "not_found": 0, "substituted": 0}
        for line in self.lines:
            counts[line.status] = counts.get(line.status, 0) + 1
        return (
            f"Quote {self.id[:8]} | {len(self.lines)} lines | "
            f"Found: {counts['found']} Not found: {counts['not_found']} "
            f"Substituted: {counts['substituted']} | "
            f"Total: {self.currency} {self.total_price:.2f}"
        )


class ERPConfig(BaseModel):
    erp_type: Literal["epicor", "sap", "oracle", "dynamics", "mock"]
    base_url: str | None = None
    api_key: str | None = None
    username: str | None = None
    password: str | None = None

    def __repr__(self) -> str:
        masked_key = "***" if self.api_key else None
        masked_pwd = "***" if self.password else None
        return (
            f"ERPConfig(erp_type={self.erp_type!r}, base_url={self.base_url!r}, "
            f"api_key={masked_key!r}, username={self.username!r}, "
            f"password={masked_pwd!r})"
        )
