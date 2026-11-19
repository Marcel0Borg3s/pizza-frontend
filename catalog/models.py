"""Product catalog mirror.

The menu is owned by the pizza_drf API (``/pizzas/``). This table is a local
mirror: ``catalog.services.refresh_catalog`` copies every pizza into a
``Product`` row so the cart, the order history and the review ownership keep
stable integer foreign keys, while ``api_id`` links each row back to the API.

Fields the API does not expose yet (``category``, ``emoji``, ``image_url``) stay
local and are only shown for rows that predate the integration.
"""

from __future__ import annotations

from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils.text import slugify


class Category(models.TextChoices):
    TRADICIONAL = "tradicional", "Tradicionais"
    ESPECIAL = "especial", "Especiais"
    VEGETARIANA = "vegetariana", "Vegetarianas"
    DOCE = "doce", "Doces"
    BEBIDA = "bebida", "Bebidas"


class Product(models.Model):
    """A pizza of the menu, mirrored from ``GET /pizzas/``."""

    api_id = models.UUIDField(
        "ID na API",
        null=True,
        blank=True,
        unique=True,
        editable=False,
        help_text="UUID da pizza em /pizzas/. Vazio em produtos legados.",
    )
    name = models.CharField("nome", max_length=120)
    slug = models.SlugField("slug", max_length=140, unique=True, blank=True)
    description = models.TextField("descrição", max_length=500)
    category = models.CharField(
        "categoria",
        max_length=20,
        choices=Category.choices,
        default=Category.TRADICIONAL,
    )
    price = models.DecimalField(
        "preço",
        max_digits=8,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    emoji = models.CharField(
        "emoji",
        max_length=8,
        default="🍕",
        help_text="Usado no card quando não há imagem.",
    )
    image_url = models.URLField("URL da imagem", blank=True)
    is_available = models.BooleanField("disponível", default=True)
    created_at = models.DateTimeField("criado em", auto_now_add=True)
    updated_at = models.DateTimeField("atualizado em", auto_now=True)

    class Meta:
        verbose_name = "produto"
        verbose_name_plural = "produtos"
        ordering = ["category", "name"]
        indexes = [models.Index(fields=["category", "is_available"])]

    def __str__(self) -> str:
        return self.name

    def save(self, *args: object, **kwargs: object) -> None:
        if not self.slug:
            self.slug = self._unique_slug()
        super().save(*args, **kwargs)

    def _unique_slug(self) -> str:
        """Build a slug that does not collide with another product."""
        base = slugify(self.name)[:135] or "produto"
        slug = base
        sibling_slugs = Product.objects.exclude(pk=self.pk)
        counter = 2
        while sibling_slugs.filter(slug=slug).exists():
            slug = f"{base}-{counter}"
            counter += 1
        return slug

    def get_absolute_url(self) -> str:
        return reverse("catalog:detail", kwargs={"slug": self.slug})

    @property
    def category_label(self) -> str:
        return self.get_category_display()

    @property
    def is_linked_to_api(self) -> bool:
        """True when this row is the mirror of a pizza that exists in the API."""
        return self.api_id is not None
