import secrets
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session, selectinload

from app.core.errors import AppError
from app.core.order_status import CUSTOMER_CANCELLABLE, LABELS, QUEUE_STATUSES, TRANSITIONS
from app.models import Order, OrderItem, OrderStatusEvent, Product, User
from app.schemas.orders import OrderCreateIn, PaymentMethod, ShipIn

_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # sem 0/O/1/I


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _not_found() -> AppError:
    return AppError(404, "Pedido não encontrado")


def _new_code(db: Session) -> str:
    while True:
        code = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(8))
        if not db.get(Order, code):
            return code


def _load(db: Session, order_id: str) -> Order:
    """Recarrega o pedido com itens e histórico (depois do commit os dados expiram)."""
    return db.scalars(
        select(Order)
        .where(Order.id == order_id)
        .options(selectinload(Order.items), selectinload(Order.history))
        .execution_options(populate_existing=True)
    ).one()


def _get_locked(db: Session, order_id: str) -> Order:
    """Trava a linha até o commit: duas ações no mesmo pedido são executadas em fila."""
    order = db.scalar(select(Order).where(Order.id == order_id).with_for_update())
    if not order:
        raise _not_found()
    return order


def _ensure_visible(order: Order, user: User) -> None:
    if user.role != "admin" and order.user_id != user.id:
        raise _not_found()  # 404 de propósito: não revela que o código existe


def _ensure_owner(order: Order, user: User) -> None:
    if order.user_id != user.id:
        raise _not_found()


def _transition(order: Order, to: str, actor: str, note: str | None = None, **fields) -> None:
    if to not in TRANSITIONS[order.status]:
        raise AppError(409, f"Transição inválida: {LABELS[order.status]} → {LABELS[to]}")
    order.status = to
    for name, value in fields.items():
        setattr(order, name, value)
    order.history.append(OrderStatusEvent(status=to, actor=actor, note=note))


# ---------- Estoque ----------

def _reserve_stock(db: Session, product_id: int, quantity: int) -> tuple[str, float]:
    """Baixa o estoque só se houver saldo, em uma única instrução (sem corrida)."""
    row = db.execute(
        update(Product)
        .where(Product.id == product_id, Product.stock >= quantity)
        .values(stock=Product.stock - quantity)
        .returning(Product.name, Product.price)
    ).first()
    if row:
        return row.name, row.price

    current = db.execute(
        select(Product.name, Product.stock).where(Product.id == product_id)
    ).first()
    if current is None:
        raise AppError(409, "Um dos produtos do carrinho não está mais disponível.")
    if current.stock == 0:
        raise AppError(409, f'"{current.name}" está sem estoque.')
    raise AppError(409, f'Estoque insuficiente para "{current.name}" (disponível: {current.stock}).')


def _release_stock(db: Session, order: Order) -> None:
    for item in order.items:
        if item.product_id is not None:  # produto excluído é ignorado
            db.execute(
                update(Product)
                .where(Product.id == item.product_id)
                .values(stock=Product.stock + item.quantity)
            )


# ---------- Cliente ----------

def create_order(db: Session, user: User, data: OrderCreateIn) -> Order:
    # Junta itens repetidos
    quantities: dict[int, int] = {}
    for item in data.items:
        quantities[item.product_id] = quantities.get(item.product_id, 0) + item.quantity
    if any(q > 99 for q in quantities.values()):
        raise AppError(422, "A quantidade de cada item deve ser de 1 a 99")

    code = _new_code(db)
    lines: list[OrderItem] = []
    total = Decimal("0")

    try:
        # Sempre na mesma ordem de produto, para evitar deadlock entre pedidos simultâneos
        for product_id in sorted(quantities):
            quantity = quantities[product_id]
            name, price = _reserve_stock(db, product_id, quantity)  # preço vem do banco
            lines.append(OrderItem(product_id=product_id, name=name, price=price, quantity=quantity))
            total += Decimal(str(price)) * quantity

        customer = data.customer
        db.add(
            Order(
                id=code,
                user_id=user.id,
                status="pending",
                total=float(total.quantize(Decimal("0.01"), ROUND_HALF_UP)),
                customer_name=customer.name,
                customer_email=customer.email,
                customer_phone=customer.phone,
                customer_cep=customer.cep,
                customer_address=customer.address,
                customer_city=customer.city,
                items=lines,
                history=[OrderStatusEvent(status="pending", actor="customer")],
            )
        )
        db.commit()
    except Exception:
        db.rollback()  # desfaz também as baixas de estoque já feitas
        raise

    return _load(db, code)


def list_user_orders(db: Session, user: User) -> list[Order]:
    return list(
        db.scalars(
            select(Order)
            .where(Order.user_id == user.id)
            .options(selectinload(Order.items), selectinload(Order.history))
            .order_by(Order.created_at.desc())
        )
    )


def get_order(db: Session, user: User, order_id: str) -> Order:
    order = db.scalars(
        select(Order)
        .where(Order.id == order_id)
        .options(selectinload(Order.items), selectinload(Order.history))
    ).first()
    if not order:
        raise _not_found()
    _ensure_visible(order, user)
    return order


def pay_order(db: Session, user: User, order_id: str, method: PaymentMethod) -> Order:
    # Pagamento SIMULADO. Com gateway real, quem confirma é o webhook do provedor, não o cliente.
    order = _get_locked(db, order_id)
    _ensure_owner(order, user)
    if order.status != "pending":
        raise AppError(409, "Este pedido não está aguardando pagamento.")

    _transition(order, "paid", "customer", payment_method=method)
    db.commit()
    return _load(db, order_id)


def _cancel(db: Session, order: Order, actor: str) -> None:
    if order.status == "cancelled":
        raise AppError(409, "Este pedido já foi cancelado.")

    needs_refund = order.status != "pending"
    _transition(
        order,
        "cancelled",
        actor,
        note="Estorno solicitado" if needs_refund else None,
        refunded=needs_refund,
    )
    _release_stock(db, order)
    db.commit()


def cancel_order(db: Session, user: User, order_id: str) -> Order:
    order = _get_locked(db, order_id)
    _ensure_owner(order, user)
    if order.status != "cancelled" and order.status not in CUSTOMER_CANCELLABLE:
        raise AppError(409, "Este pedido já está em andamento e não pode mais ser cancelado.")

    _cancel(db, order, "customer")
    return _load(db, order_id)


# ---------- Admin ----------

def _like(term: str) -> str:
    escaped = term.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def admin_list_orders(
    db: Session, status: str | None, search: str | None, page: int, page_size: int
) -> tuple[list[Order], int]:
    stmt = select(Order)
    if status:
        stmt = stmt.where(Order.status == status)
    if search and search.strip():
        like = _like(search)
        stmt = stmt.where(
            or_(
                Order.id.ilike(like, escape="\\"),
                Order.customer_name.ilike(like, escape="\\"),
                Order.customer_email.ilike(like, escape="\\"),
                Order.customer_city.ilike(like, escape="\\"),
            )
        )

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0

    # Fila de trabalho: quem espera há mais tempo primeiro. Demais visões: mais recentes primeiro.
    order_by = Order.updated_at.asc() if status in QUEUE_STATUSES else Order.created_at.desc()
    rows = db.scalars(
        stmt.options(selectinload(Order.items), selectinload(Order.history))
        .order_by(order_by, Order.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(rows), total


def order_summary(db: Session) -> dict[str, int]:
    counts = {status: 0 for status in LABELS}
    for status, count in db.execute(select(Order.status, func.count()).group_by(Order.status)):
        counts[status] = count
    return counts


def start_processing(db: Session, order_id: str) -> Order:
    order = _get_locked(db, order_id)
    _transition(order, "processing", "admin")
    db.commit()
    return _load(db, order_id)


def ship_order(db: Session, order_id: str, data: ShipIn) -> Order:
    order = _get_locked(db, order_id)
    _transition(
        order,
        "shipped",
        "admin",
        note=f"{data.carrier} · {data.tracking_code}",
        carrier=data.carrier,
        tracking_code=data.tracking_code,
        estimated_delivery=data.estimated_delivery,
        shipped_at=_now(),
    )
    db.commit()
    return _load(db, order_id)


def deliver_order(db: Session, order_id: str) -> Order:
    order = _get_locked(db, order_id)
    _transition(order, "delivered", "admin", delivered_at=_now())
    db.commit()
    return _load(db, order_id)


def admin_cancel_order(db: Session, order_id: str) -> Order:
    order = _get_locked(db, order_id)
    _cancel(db, order, "admin")
    return _load(db, order_id)