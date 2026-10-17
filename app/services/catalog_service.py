from urllib.parse import quote

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models import Category, Product
from app.schemas.catalog import ProductIn, SortOption

_SORTS = {
    "name": func.lower(Product.name).asc(),
    "price_asc": Product.price.asc(),
    "price_desc": Product.price.desc(),
}


def placeholder_image(name: str) -> str:
    return f"https://placehold.co/600x400/e2e8f0/334155?text={quote(name)}"


def list_categories(db: Session) -> list[Category]:
    return list(db.scalars(select(Category).order_by(Category.id)))


def list_products(
    db: Session, search: str | None, category_id: int | None, sort: SortOption
) -> list[Product]:
    stmt = select(Product)

    if search and search.strip():
        # Escapa % e _ para a busca ser literal
        term = search.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        like = f"%{term}%"
        stmt = stmt.where(
            or_(Product.name.ilike(like, escape="\\"), Product.brand.ilike(like, escape="\\"))
        )
    if category_id:
        stmt = stmt.where(Product.category_id == category_id)

    return list(db.scalars(stmt.order_by(_SORTS[sort], Product.id)))


def get_product(db: Session, product_id: int) -> Product:
    product = db.get(Product, product_id)
    if not product:
        raise AppError(404, "Produto não encontrado")
    return product


def _ensure_category(db: Session, category_id: int) -> None:
    if not db.get(Category, category_id):
        raise AppError(422, "Categoria inexistente")


def create_product(db: Session, data: ProductIn) -> Product:
    _ensure_category(db, data.category_id)
    values = data.model_dump()
    values["image_url"] = values["image_url"] or placeholder_image(values["name"])

    product = Product(**values)
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


def update_product(db: Session, product_id: int, data: ProductIn) -> Product:
    product = get_product(db, product_id)
    _ensure_category(db, data.category_id)

    values = data.model_dump()
    values["image_url"] = values["image_url"] or placeholder_image(values["name"])
    for field, value in values.items():
        setattr(product, field, value)

    db.commit()
    db.refresh(product)
    return product


def delete_product(db: Session, product_id: int) -> None:
    product = get_product(db, product_id)
    db.delete(product)
    db.commit()