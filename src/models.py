from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class HotelSearchRequest(BaseModel):
    destino: str = Field(min_length=2, max_length=120)
    dataCheckin: date
    dataCheckout: date
    adultos: int = Field(default=2, ge=1, le=10)
    criancas: int = Field(default=0, ge=0, le=10)
    limite_resultados: int = Field(default=20, ge=1, le=50)

    @model_validator(mode="after")
    def validate_dates(self) -> "HotelSearchRequest":
        if self.dataCheckout <= self.dataCheckin:
            raise ValueError("dataCheckout deve ser maior que dataCheckin")
        return self


class HotelItem(BaseModel):
    model_config = ConfigDict(
        json_encoders={Decimal: lambda value: float(value)}
    )

    nomeDoHotel: str
    local: str
    precos: dict[str, Decimal]


class SearchResponse(BaseModel):
    status: Literal["success", "partial"]
    timestamp: datetime
    quantidade_resultados: int
    hoteis: list[HotelItem]
    avisos: list[str] = []

    @classmethod
    def now(cls) -> datetime:
        return datetime.now(timezone.utc)


class HealthResponse(BaseModel):
    status: Literal["ok"]
    scraper_available: bool
    timestamp: datetime
