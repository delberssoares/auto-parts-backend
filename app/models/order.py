from datetime import date, datetime, timezone

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (CheckConstraint("total > 0", name="ck_orders_total_positive"),)

    id: Mapped[str] = mapped_column(String(12), primary_key=True)  # código público
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    total: Mapped[float] = mapped_column(Numeric(10, 2, asdecimal=False))
    payment_method: Mapped[str | None] = mapped_column(String(10), default=None)
    refunded: Mapped[bool] = mapped_column(default=False)

    # Cópia dos dados de entrega no momento da compra
    customer_name: Mapped[str] = mapped_column(String(120))
    customer_email: Mapped[str] = mapped_column(String(255))
    customer_phone: Mapped[str] = mapped_column(String(30))
    customer_cep: Mapped[str] = mapped_column(String(12))
    customer_address: Mapped[str] = mapped_column(String(255))
    customer_city: Mapped[str] = mapped_column(String(100))

    carrier: Mapped[str | None] = mapped_column(String(60), default=None)
    tracking_code: Mapped[str | None] = mapped_column(String(40), default=None)
    estimated_delivery: Mapped[date | None] = mapped_column(Date, default=None)
    shipped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    items: Mapped[list["OrderItem"]] = relationship(
        cascade="all, delete-orphan", order_by="OrderItem.id"
    )
    history: Mapped[list["OrderStatusEvent"]] = relationship(
        cascade="all, delete-orphan", order_by="OrderStatusEvent.id"
    )

    # Mantêm o formato que o front já usa (customer e shipping aninhados)
    @property
    def customer(self) -> dict:
        return {
            "name": self.customer_name,
            "email": self.customer_email,
            "phone": self.customer_phone,
            "cep": self.customer_cep,
            "address": self.customer_address,
            "city": self.customer_city,
        }

    @property
    def shipping(self) -> dict | None:
        if not self.carrier or not self.tracking_code or not self.shipped_at:
            return None
        return {
            "carrier": self.carrier,
            "tracking_code": self.tracking_code,
            "shipped_at": self.shipped_at,
            "estimated_delivery": self.estimated_delivery,
            "delivered_at": self.delivered_at,
        }


class OrderItem(Base):
    __tablename__ = "order_items"
    __table_args__ = (CheckConstraint("quantity > 0", name="ck_order_items_quantity_positive"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    # Se o produto for excluído, o item continua no histórico com nome e preço da compra
    product_id: Mapped[int | None] = mapped_column(
        ForeignKey("products.id", ondelete="SET NULL"), index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    price: Mapped[float] = mapped_column(Numeric(10, 2, asdecimal=False))
    quantity: Mapped[int]


class OrderStatusEvent(Base):
    __tablename__ = "order_status_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(20))
    actor: Mapped[str] = mapped_column(String(10))  # customer | admin | system
    note: Mapped[str | None] = mapped_column(String(255), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)