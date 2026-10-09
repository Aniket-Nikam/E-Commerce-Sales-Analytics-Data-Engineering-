from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator


class OrderEvent(BaseModel):
    event_id: UUID = Field(default_factory=uuid4)
    event_time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    order_id: str = Field(min_length=3, max_length=64)
    customer_id: str = Field(min_length=3, max_length=64)
    product_id: str = Field(min_length=2, max_length=64)
    category: str = Field(min_length=2, max_length=64)
    quantity: int = Field(gt=0, le=100)
    unit_price: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    discount_pct: Decimal = Field(default=Decimal("0"), ge=0, le=Decimal("0.80"))
    region: str = Field(min_length=2, max_length=32)
    sales_channel: str = Field(min_length=2, max_length=32)

    @field_validator(
        "order_id",
        "customer_id",
        "product_id",
        "category",
        "region",
        "sales_channel",
    )
    @classmethod
    def normalize_text(cls, value: str) -> str:
        normalized = " ".join(value.strip().split())
        if not normalized:
            raise ValueError("value cannot be blank")
        return normalized

    @property
    def net_revenue(self) -> Decimal:
        return (self.unit_price * self.quantity * (Decimal("1") - self.discount_pct)).quantize(
            Decimal("0.01")
        )

