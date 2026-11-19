"""Server side calls to the pizza_drf ``/pizzas/`` endpoints.

The API owns the menu. ``catalog.services`` mirrors every row returned here into
the local ``Product`` table (see ``catalog.models``) so the cart and the order
history keep integer foreign keys.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from typing import Any

from core.api import ApiError, api_client

PIZZA_FIELDS: tuple[str, ...] = ("flavor", "description", "price")


def rows(payload: Any) -> list[dict[str, Any]]:
    """Accept both a plain list and a paginated ``{"results": [...]}`` body."""
    if isinstance(payload, dict):
        payload = payload.get("results", [])
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    return []


def format_price(value: Any) -> str:
    """Return the price as the two decimal string ``DecimalField`` expects."""
    try:
        amount = Decimal(str(value).replace(",", ".")).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError, TypeError):
        return "0.00"
    return f"{amount:.2f}"


def build_payload(*, flavor: str, description: str, price: Any) -> dict[str, str]:
    """Keep only the fields the API accepts, already normalized."""
    return {
        "flavor": str(flavor).strip()[:50],
        "description": str(description).strip(),
        "price": format_price(price),
    }


def list_pizzas() -> list[dict[str, Any]]:
    """``GET /pizzas/``."""
    return rows(api_client.get("pizzas/"))


def fetch_pizza(api_id: str) -> dict[str, Any] | None:
    """``GET /pizzas/<uuid>/`` — ``None`` when the API answers 404."""
    try:
        row = api_client.get(f"pizzas/{api_id}/")
    except ApiError as exc:
        if exc.status_code == 404:
            return None
        raise
    return row if isinstance(row, dict) else None


def create_pizza(payload: Mapping[str, str]) -> dict[str, Any]:
    """``POST /pizzas/`` — returns the created pizza."""
    row = api_client.post("pizzas/", json=dict(payload))
    if not isinstance(row, dict) or "id" not in row:
        raise ApiError("A API retornou uma pizza inválida.")
    return row


def update_pizza(api_id: str, payload: Mapping[str, str]) -> dict[str, Any]:
    """``PATCH /pizzas/<uuid>/`` — returns the updated pizza."""
    row = api_client.patch(f"pizzas/{api_id}/", json=dict(payload))
    if not isinstance(row, dict) or "id" not in row:
        raise ApiError("A API retornou uma pizza inválida.")
    return row


def delete_pizza(api_id: str) -> None:
    """``DELETE /pizzas/<uuid>/``."""
    api_client.delete(f"pizzas/{api_id}/")


__all__ = [
    "PIZZA_FIELDS",
    "build_payload",
    "create_pizza",
    "delete_pizza",
    "fetch_pizza",
    "format_price",
    "list_pizzas",
    "rows",
    "update_pizza",
]
