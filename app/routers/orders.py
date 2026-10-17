from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_admin
from app.core.order_status import OrderStatus
from app.db.session import get_db
from app.models import User
from app.schemas.orders import (
    OrderCreateIn,
    OrderOut,
    OrderPageOut,
    OrderSummaryOut,
    PayIn,
    ShipIn,
)
from app.services import order_service

router = APIRouter(prefix="/orders", tags=["orders"])
admin_router = APIRouter(
    prefix="/admin/orders", tags=["admin-orders"], dependencies=[Depends(require_admin)]
)


# ---------- Cliente ----------

@router.post("", response_model=OrderOut, status_code=201)
def create_order(
    data: OrderCreateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    return order_service.create_order(db, user, data)


@router.get("", response_model=list[OrderOut])
def list_my_orders(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return order_service.list_user_orders(db, user)


@router.get("/{order_id}", response_model=OrderOut)
def get_order(order_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return order_service.get_order(db, user, order_id)


@router.post("/{order_id}/pay", response_model=OrderOut)
def pay_order(
    order_id: str,
    data: PayIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return order_service.pay_order(db, user, order_id, data.method)


@router.post("/{order_id}/cancel", response_model=OrderOut)
def cancel_order(
    order_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    return order_service.cancel_order(db, user, order_id)


# ---------- Admin ----------

@admin_router.get("", response_model=OrderPageOut)
def admin_list_orders(
    status: OrderStatus | None = None,
    search: str | None = Query(None, max_length=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    items, total = order_service.admin_list_orders(db, status, search, page, page_size)
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@admin_router.get("/summary", response_model=OrderSummaryOut)
def admin_order_summary(db: Session = Depends(get_db)):
    return {"counts": order_service.order_summary(db)}


@admin_router.post("/{order_id}/start-processing", response_model=OrderOut)
def start_processing(order_id: str, db: Session = Depends(get_db)):
    return order_service.start_processing(db, order_id)


@admin_router.post("/{order_id}/ship", response_model=OrderOut)
def ship_order(order_id: str, data: ShipIn, db: Session = Depends(get_db)):
    return order_service.ship_order(db, order_id, data)


@admin_router.post("/{order_id}/deliver", response_model=OrderOut)
def deliver_order(order_id: str, db: Session = Depends(get_db)):
    return order_service.deliver_order(db, order_id)


@admin_router.post("/{order_id}/cancel", response_model=OrderOut)
def admin_cancel_order(order_id: str, db: Session = Depends(get_db)):
    return order_service.admin_cancel_order(db, order_id)