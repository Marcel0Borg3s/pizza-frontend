"""Single entry point for catalog data.

The menu is owned by the pizza_drf API (``/pizzas/``). ``refresh_catalog``
mirrors the remote pizzas into the local ``Product`` table and every read below
queries that mirror, so views, templates, the cart, the orders and the owner
panel share one API.

Write operations (``create_pizza``, ``update_pizza``, ``delete_pizza``) go to
the API first and only then touch the mirror: the API is the source of truth.
"""

from __future__ import annotations

import logging
import uuid
from decimal import Decimal, InvalidOperation
from typing import Any

from django.db.models import Q, QuerySet

from catalog import api as pizza_api
from catalog.models import Category, Product

logger = logging.getLogger(__name__)


def _as_decimal(value: Any) -> Decimal:
    """Convert an API price (string or number) into a safe Decimal."""
    try:
        return Decimal(str(value).replace(",", ".")).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0.00")


def _parse_api_id(value: Any) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        return None


def _apply(row: dict[str, Any], product: Product) -> None:
    """Copy the API fields onto the mirror row (slug and extras stay local)."""
    product.name = str(row.get("flavor") or "").strip()[:120] or "Pizza"
    product.description = str(row.get("description") or "").strip()
    product.price = _as_decimal(row.get("price"))
    product.is_available = True


def _upsert_pizza(
    row: dict[str, Any], adoptable: dict[str, Product] | None = None
) -> tuple[Product, bool]:
    """Mirror one API pizza. Returns ``(product, created)``.

    A legacy row (no ``api_id``) with the same name is adopted instead of
    duplicated, which preserves its local slug, emoji and category.
    """
    api_id = _parse_api_id(row.get("id"))
    if api_id is None:
        raise ValueError("Pizza sem id válido.")

    product = Product.objects.filter(api_id=api_id).first()
    if product is not None:
        _apply(row, product)
        product.save()
        return product, False

    flavor = str(row.get("flavor") or "").strip()
    product = None
    if adoptable:
        product = adoptable.pop(flavor.lower(), None)
    if product is None:
        product = Product(api_id=api_id)
    else:
        product.api_id = api_id
    _apply(row, product)
    product.save()
    return product, True


def refresh_catalog() -> dict[str, int]:
    """``GET /pizzas/`` and mirror the whole menu locally.

    Pizzas that disappeared from the API (and local rows that predate the
    integration) are marked unavailable instead of deleted, because old orders
    still point at them. Raises ``ApiError`` when the API is unreachable; in
    that case the mirror is left untouched.
    """
    remote_rows = pizza_api.list_pizzas()
    legacy = {
        product.name.strip().lower(): product
        for product in Product.objects.filter(api_id__isnull=True).order_by("pk")
    }

    seen: list[uuid.UUID] = []
    created = updated = 0
    for row in remote_rows:
        try:
            product, was_created = _upsert_pizza(row, legacy)
        except ValueError:
            logger.warning("Ignoring pizza without a valid id: %s", row)
            continue
        seen.append(product.api_id)
        created += int(was_created)
        updated += int(not was_created)

    hidden = Product.objects.exclude(api_id__in=seen).filter(is_available=True).update(
        is_available=False
    )
    logger.info(
        "Catalog refreshed from API: %s created, %s updated, %s hidden",
        created,
        updated,
        hidden,
    )
    return {"total": len(seen), "created": created, "updated": updated, "hidden": hidden}


def list_products(
    *,
    search: str | None = None,
    category: str | None = None,
    only_available: bool = True,
) -> QuerySet[Product]:
    """Return the mirrored catalog filtered by free text and category."""
    queryset = Product.objects.all()
    if only_available:
        queryset = queryset.filter(is_available=True)
    if search:
        term = search.strip()
        if term:
            queryset = queryset.filter(Q(name__icontains=term) | Q(description__icontains=term))
    if category and category in Category.values:
        queryset = queryset.filter(category=category)
    return queryset.distinct()


def get_product(slug: str) -> Product | None:
    """Return an available product by slug, or ``None``."""
    return Product.objects.filter(slug=slug, is_available=True).first()


def get_product_by_api_id(api_id: Any) -> Product | None:
    """Return the mirror row of an API pizza, or ``None``."""
    parsed = _parse_api_id(api_id)
    if parsed is None:
        return None
    return Product.objects.filter(api_id=parsed).first()


def create_pizza(*, flavor: str, description: str, price: Any) -> Product:
    """``POST /pizzas/`` then mirror the created pizza."""
    payload = pizza_api.build_payload(flavor=flavor, description=description, price=price)
    row = pizza_api.create_pizza(payload)
    product, _ = _upsert_pizza(row)
    return product


def update_pizza(*, api_id: str, flavor: str, description: str, price: Any) -> Product:
    """``PATCH /pizzas/<uuid>/`` then mirror the updated pizza."""
    payload = pizza_api.build_payload(flavor=flavor, description=description, price=price)
    row = pizza_api.update_pizza(str(api_id), payload)
    product, _ = _upsert_pizza(row)
    return product


def delete_pizza(api_id: str) -> None:
    """``DELETE /pizzas/<uuid>/`` and unlink the mirror row.

    The local row stays (order history and the protected foreign keys depend on
    it) but loses the API link and leaves the menu.
    """
    pizza_api.delete_pizza(str(api_id))
    parsed = _parse_api_id(api_id)
    if parsed is None:
        return
    Product.objects.filter(api_id=parsed).update(api_id=None, is_available=False)


def categories() -> list[dict[str, str]]:
    """Categories for the filter bar."""
    return [{"value": value, "label": label} for value, label in Category.choices]
