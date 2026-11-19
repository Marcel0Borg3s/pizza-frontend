"""Orders and their items.

Prices are stored as snapshots: a later change in the catalog never rewrites
the value a customer paid.
"""

from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.db import models

from catalog.models import Product


class Order(models.Model):
    """A delivery order placed by an authenticated customer."""

    class Status(models.TextChoices):
        PENDING = "pending", "Aguardando confirmação"
        CONFIRMED = "confirmed", "Confirmado"
        DELIVERED = "delivered", "Entregue"
        CANCELLED = "cancelled", "Cancelado"

    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="orders",
        verbose_name="cliente",
    )
    status = models.CharField(
        "status", max_length=20, choices=Status.choices, default=Status.PENDING
    )
    customer_name = models.CharField("nome", max_length=200)
    phone = models.CharField("telefone", max_length=20)
    address = models.CharField("endereço", max_length=100)
    number = models.CharField("número", max_length=10)
    neighborhood = models.CharField("bairro", max_length=100)
    city = models.CharField("cidade", max_length=100)
    notes = models.TextField("observações", max_length=300, blank=True)
    total = models.DecimalField("total", max_digits=9, decimal_places=2, default=Decimal("0.00"))
    created_at = models.DateTimeField("criado em", auto_now_add=True)
    updated_at = models.DateTimeField("atualizado em", auto_now=True)

    class Meta:
        verbose_name = "pedido"
        verbose_name_plural = "pedidos"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["customer", "-created_at"])]

    def __str__(self) -> str:
        return f"Pedido #{self.pk} — {self.customer_name}"

    @property
    def total_items(self) -> int:
        return sum(item.quantity for item in self.items.all())

    @property
    def can_cancel(self) -> bool:
        return self.status == self.Status.PENDING

    @property
    def status_badge_class(self) -> str:
        """Tailwind classes for the status badge."""
        badge_classes = {
            self.Status.PENDING: (
                "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300"
            ),
            self.Status.CONFIRMED: ("bg-sky-100 text-sky-800 dark:bg-sky-900/40 dark:text-sky-300"),
            self.Status.DELIVERED: (
                "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300"
            ),
            self.Status.CANCELLED: (
                "bg-rose-100 text-rose-800 dark:bg-rose-900/40 dark:text-rose-300"
            ),
        }
        return badge_classes.get(
            self.status, "bg-stone-100 text-stone-700 dark:bg-stone-800 dark:text-stone-300"
        )


class OrderItem(models.Model):
    """One product line inside an order, with the price of the moment."""

    order = models.ForeignKey(
        Order, on_delete=models.CASCADE, related_name="items", verbose_name="pedido"
    )
    product = models.ForeignKey(
        Product, on_delete=models.PROTECT, related_name="order_items", verbose_name="produto"
    )
    product_name = models.CharField("nome do produto", max_length=120)
    quantity = models.PositiveSmallIntegerField("quantidade", default=1)
    unit_price = models.DecimalField("preço unitário", max_digits=8, decimal_places=2)

    class Meta:
        verbose_name = "item do pedido"
        verbose_name_plural = "itens do pedido"
        ordering = ["pk"]

    def __str__(self) -> str:
        return f"{self.quantity}x {self.product_name}"

    @property
    def subtotal(self) -> Decimal:
        return self.unit_price * self.quantity

    @property
    def has_review(self) -> bool:
        return hasattr(self, "review")
