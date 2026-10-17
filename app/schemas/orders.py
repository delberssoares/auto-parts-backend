import re
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, field_validator

from app.core.order_status import OrderStatus
from app.schemas.auth import Email
from app.schemas.common import bounded

PaymentMethod = Literal["pix", "card"]


def _digits(label: str, min_len: int, max_len: int) -> AfterValidator:
    def check(v: str) -> str:
        v = v.strip()
        count = len(re.sub(r"\D", "", v))
        if not re.fullmatch(r"[\d\s()+\-.]+", v) or not min_len <= count <= max_len:
            raise ValueError(f"{label} inválido")
        return v

    return AfterValidator(check)


def _check_quantity(v: int) -> int:
    if not 1 <= v <= 99:
        raise ValueError("A quantidade de cada item deve ser de 1 a 99")
    return v


def _check_items(v: list["OrderItemIn"]) -> list["OrderItemIn"]:
    if not v:
        raise ValueError("O pedido precisa ter ao menos um item")
    if len(v) > 50:
        raise ValueError("Itens demais no mesmo pedido")
    return v


# ---------- Entrada ----------

class CustomerIn(BaseModel):
    name: Annotated[str, bounded("Nome", 3, 120)]
    email: Email
    phone: Annotated[str, _digits("Telefone", 10, 11)]
    cep: Annotated[str, _digits("CEP", 8, 8)]
    address: Annotated[str, bounded("Endereço", 5, 255)]
    city: Annotated[str, bounded("Cidade", 2, 100)]


class OrderItemIn(BaseModel):
    product_id: int
    quantity: Annotated[int, AfterValidator(_check_quantity)]


class OrderCreateIn(BaseModel):
    customer: CustomerIn
    items: Annotated[list[OrderItemIn], AfterValidator(_check_items)]


class PayIn(BaseModel):
    method: PaymentMethod


class ShipIn(BaseModel):
    carrier: Annotated[str, bounded("Transportadora", 2, 60)]
    tracking_code: str
    estimated_delivery: date | None = None

    @field_validator("tracking_code")
    @classmethod
    def _check_code(cls, v: str) -> str:
        v = v.strip().upper()
        if not re.fullmatch(r"[A-Z0-9-]{8,30}", v):
            raise ValueError("Código de rastreio inválido (8 a 30 letras, números ou hífen)")
        return v

    @field_validator("estimated_delivery", mode="before")
    @classmethod
    def _blank_to_none(cls, v):
        return None if v in ("", None) else v

    @field_validator("estimated_delivery")
    @classmethod
    def _not_past(cls, v: date | None) -> date | None:
        if v and v < date.today():
            raise ValueError("A previsão de entrega não pode ser no passado")
        return v


# ---------- Saída ----------

class OrderItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int | None
    name: str
    price: float
    quantity: int


class CustomerOut(BaseModel):
    name: str
    email: str
    phone: str
    cep: str
    address: str
    city: str


class ShippingOut(BaseModel):
    carrier: str
    tracking_code: str
    shipped_at: datetime
    estimated_delivery: date | None
    delivered_at: datetime | None


class StatusEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status: OrderStatus
    by: Literal["customer", "admin", "system"] = Field(validation_alias="actor")
    at: datetime = Field(validation_alias="created_at")
    note: str | None


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    status: OrderStatus
    total: float
    payment_method: PaymentMethod | None
    refunded: bool
    customer: CustomerOut
    items: list[OrderItemOut]
    shipping: ShippingOut | None
    history: list[StatusEventOut]
    created_at: datetime


class OrderPageOut(BaseModel):
    items: list[OrderOut]
    total: int
    page: int
    page_size: int


class OrderSummaryOut(BaseModel):
    counts: dict[OrderStatus, int]