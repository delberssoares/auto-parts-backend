import re
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict
from app.schemas.common import bounded as _bounded


SortOption = Literal["name", "price_asc", "price_desc"]


def _check_price(v: float) -> float:
    if v <= 0:
        raise ValueError("O preço deve ser maior que zero")
    if v > 1_000_000:
        raise ValueError("Preço acima do permitido")
    return round(v, 2)


def _check_stock(v: int) -> int:
    if v < 0:
        raise ValueError("O estoque não pode ser negativo")
    return v


def _check_image_url(v: str) -> str:
    v = v.strip()
    if v and not re.match(r"^https?://", v):
        raise ValueError("URL da imagem inválida")
    if len(v) > 500:
        raise ValueError("URL da imagem muito longa")
    return v


class ProductIn(BaseModel):
    name: Annotated[str, _bounded("Nome", 3, 120)]
    brand: Annotated[str, _bounded("Marca", 2, 60)]
    description: Annotated[str, _bounded("Descrição", 10, 2000)]
    price: Annotated[float, AfterValidator(_check_price)]
    stock: Annotated[int, AfterValidator(_check_stock)]
    image_url: Annotated[str, AfterValidator(_check_image_url)] = ""
    category_id: int


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    brand: str
    description: str
    price: float
    stock: int
    image_url: str
    category_id: int


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str