"""Cart and checkout services.

The cart lives in the session and stores only product ids and quantities.
Prices are always read from the database at checkout time, so a hand edited
session cookie cannot change the amount charged.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from django.db import transaction

from catalog.models import Product
from orders.models import Order, OrderItem

CART_SESSION_KEY = "cart"
MAX_QUANTITY = 20


class CartError(Exception):
    """Base error for cart operations."""


class EmptyCartError(CartError):
    """Raised when checkout runs with an empty cart."""


class UnavailableProductError(CartError):
    """Raised when a product became unavailable before checkout."""

    def __init__(self, product_name: str) -> None:
        super().__init__(f"{product_name} não está disponível no momento.")
        self.product_name = product_name


@dataclass(frozen=True)
class CartLine:
    """A product with the quantity chosen by the customer."""

    product: Product
    quantity: int

    @property
    def subtotal(self) -> Decimal:
        return self.product.price * self.quantity


def _clamp(quantity: int) -> int:
    return max(1, min(MAX_QUANTITY, int(quantity)))


class Cart:
    """Session backed cart that never trusts prices from the client."""

    def __init__(self, session: Any) -> None:
        self.session = session
        raw = session.get(CART_SESSION_KEY, {})
        self._items: dict[str, int] = {}
        if isinstance(raw, dict):
            for key, value in raw.items():
                try:
                    quantity = _clamp(int(value))
                except (TypeError, ValueError):
                    continue
                if str(key).isdigit():
                    self._items[str(key)] = quantity

    # -- persistence -------------------------------------------------------

    def _save(self) -> None:
        self.session[CART_SESSION_KEY] = self._items
        self.session.modified = True

    # -- mutations ---------------------------------------------------------

    def add(self, product_id: int, quantity: int = 1) -> None:
        key = str(int(product_id))
        self._items[key] = _clamp(self._items.get(key, 0) + int(quantity))
        self._save()

    def set_quantity(self, product_id: int, quantity: int) -> None:
        key = str(int(product_id))
        if int(quantity) <= 0:
            self.remove(product_id)
            return
        self._items[key] = _clamp(quantity)
        self._save()

    def remove(self, product_id: int) -> None:
        self._items.pop(str(int(product_id)), None)
        self._save()

    def clear(self) -> None:
        self._items = {}
        self._save()

    # -- reads -------------------------------------------------------------

    def __bool__(self) -> bool:
        return bool(self._items)

    def __len__(self) -> int:
        return sum(self._items.values())

    @property
    def quantity_total(self) -> int:
        return sum(self._items.values())

    def lines(self) -> list[CartLine]:
        if not self._items:
            return []
        product_ids = [int(key) for key in self._items]
        products = Product.objects.in_bulk(product_ids)
        lines: list[CartLine] = []
        changed = False
        for key, quantity in self._items.items():
            product = products.get(int(key))
            if product is None or not product.is_available:
                changed = True
                continue
            lines.append(CartLine(product=product, quantity=quantity))
        if changed:
            self._items = {str(line.product.pk): line.quantity for line in lines}
            self._save()
        return lines

    @property
    def total(self) -> Decimal:
        return sum((line.subtotal for line in self.lines()), Decimal("0.00"))


def cart_quantity(session: Any) -> int:
    """Total items, safe to call from any page."""
    if session is None:
        return 0
    return len(Cart(session))


@transaction.atomic
def create_order(
    *,
    user: Any,
    cart: Cart,
    delivery: Mapping[str, str],
    notes: str = "",
) -> Order:
    """Create the order from the cart, recalculating every price server side."""
    lines = cart.lines()
    if not lines:
        raise EmptyCartError("Seu carrinho está vazio.")

    order = Order.objects.create(
        customer=user,
        customer_name=str(delivery["customer_name"])[:200],
        phone=str(delivery["phone"])[:20],
        address=str(delivery["address"])[:100],
        number=str(delivery["number"])[:10],
        neighborhood=str(delivery["neighborhood"])[:100],
        city=str(delivery["city"])[:100],
        notes=str(notes or "")[:300],
        total=Decimal("0.00"),
    )

    total = Decimal("0.00")
    for line in lines:
        if not line.product.is_available:
            raise UnavailableProductError(line.product.name)
        OrderItem.objects.create(
            order=order,
            product=line.product,
            product_name=line.product.name,
            quantity=line.quantity,
            unit_price=line.product.price,
        )
        total += line.subtotal

    order.total = total
    order.save(update_fields=["total", "updated_at"])
    cart.clear()
    return order
