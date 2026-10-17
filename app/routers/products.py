from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import require_admin
from app.db.session import get_db
from app.schemas.catalog import CategoryOut, ProductIn, ProductOut, SortOption
from app.services import catalog_service

categories_router = APIRouter(prefix="/categories", tags=["catalog"])
router = APIRouter(prefix="/products", tags=["catalog"])


@categories_router.get("", response_model=list[CategoryOut])
def list_categories(db: Session = Depends(get_db)):
    return catalog_service.list_categories(db)


@router.get("", response_model=list[ProductOut])
def list_products(
    search: str | None = Query(None, max_length=100),
    category_id: int | None = None,
    sort: SortOption = "name",
    db: Session = Depends(get_db),
):
    return catalog_service.list_products(db, search, category_id, sort)


@router.get("/{product_id}", response_model=ProductOut)
def get_product(product_id: int, db: Session = Depends(get_db)):
    return catalog_service.get_product(db, product_id)


@router.post(
    "", response_model=ProductOut, status_code=201, dependencies=[Depends(require_admin)]
)
def create_product(data: ProductIn, db: Session = Depends(get_db)):
    return catalog_service.create_product(db, data)


@router.put(
    "/{product_id}", response_model=ProductOut, dependencies=[Depends(require_admin)]
)
def update_product(product_id: int, data: ProductIn, db: Session = Depends(get_db)):
    return catalog_service.update_product(db, product_id, data)


@router.delete("/{product_id}", status_code=204, dependencies=[Depends(require_admin)])
def delete_product(product_id: int, db: Session = Depends(get_db)) -> None:
    catalog_service.delete_product(db, product_id)