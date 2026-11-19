"""Product reviews.

The public list is read from the pizza_drf API (``GET /reviews/``). This local
model keeps the author, the order item and the date, which the API does not
store yet, and ``api_id`` links it to the remote review. A review is tied to one
purchased item, so only who really ordered can write it, and only once per item.
"""

from __future__ import annotations

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from catalog.models import Product
from orders.models import OrderItem


class Review(models.Model):
    """A 1 to 5 star review for a product bought in an order."""

    order_item = models.OneToOneField(
        OrderItem,
        on_delete=models.CASCADE,
        related_name="review",
        verbose_name="item do pedido",
    )
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="reviews", verbose_name="produto"
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="reviews",
        verbose_name="autor",
    )
    rating = models.PositiveSmallIntegerField(
        "nota",
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    comment = models.TextField("comentário", max_length=500)
    created_at = models.DateTimeField("criado em", auto_now_add=True)
    api_id = models.CharField(
        "ID na API",
        max_length=64,
        null=True,
        blank=True,
        unique=True,
        editable=False,
        help_text="ID da avaliação em /reviews/ (inteiro na API). Vazio em avaliações antigas.",
    )

    class Meta:
        verbose_name = "avaliação"
        verbose_name_plural = "avaliações"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["product", "-created_at"])]

    def __str__(self) -> str:
        return f"{self.product} — {self.rating}/5 por {self.author}"

    @property
    def author_display(self) -> str:
        """Public name: first name plus the last initial."""
        full_name = self.author.get_full_name().strip()
        if not full_name:
            return self.author.get_username()
        parts = full_name.split()
        if len(parts) == 1:
            return parts[0]
        return f"{parts[0]} {parts[-1][0]}."
