from typing import Literal

OrderStatus = Literal["pending", "paid", "processing", "shipped", "delivered", "cancelled"]

LABELS: dict[str, str] = {
    "pending": "Aguardando pagamento",
    "paid": "Pago",
    "processing": "Em separação",
    "shipped": "Enviado",
    "delivered": "Entregue",
    "cancelled": "Cancelado",
}

TRANSITIONS: dict[str, set[str]] = {
    "pending": {"paid", "cancelled"},
    "paid": {"processing", "cancelled"},
    "processing": {"shipped", "cancelled"},
    "shipped": {"delivered"},  # depois de enviado não cancela (seria devolução)
    "delivered": set(),
    "cancelled": set(),
}

CUSTOMER_CANCELLABLE = {"pending", "paid"}
QUEUE_STATUSES = {"paid", "processing", "shipped"}