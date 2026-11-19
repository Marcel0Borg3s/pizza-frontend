"""Review queries: the public list comes from the pizza_drf API.

``GET /reviews/`` returns ``{id, pizza, stars, comment, created_at}``. The API
does not know who wrote the review, so each remote row is enriched with the
local mirror (``Review.api_id``) when the review was written through this front.

TODO(reviews-media): the average and the star breakdown will be configured
later. ``rating_summary`` deliberately returns ``average = None`` so no template
invents a number before that rule exists.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

from django.utils.dateparse import parse_datetime

from catalog.models import Product
from core.api import ApiError, api_client
from reviews.models import Review

GUEST_LABEL = "Cliente"


def _rows(payload: Any) -> list[dict[str, Any]]:
    """Accept both a plain list and a paginated ``{"results": [...]}`` body."""
    if isinstance(payload, dict):
        payload = payload.get("results", [])
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    return []


def remote_rows(pizza_api_id: Any = None) -> list[dict[str, Any]]:
    """``GET /reviews/``, optionally filtered by pizza (``?pizza=<uuid>``)."""
    params = {"pizza": str(pizza_api_id)} if pizza_api_id else None
    return _rows(api_client.get("reviews/", params=params))


def _created_at(row: Mapping[str, Any]) -> datetime | None:
    value = row.get("created_at")
    return parse_datetime(str(value)) if value else None


def _decorate(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Add the local author, date and product link to each remote review."""
    local_reviews = {
        str(review.api_id): review
        for review in Review.objects.select_related("author").exclude(api_id__isnull=True)
    }
    products = {
        str(product.api_id): product
        for product in Product.objects.exclude(api_id__isnull=True)
    }

    decorated: list[dict[str, Any]] = []
    for row in rows:
        local_review = local_reviews.get(str(row.get("id")))
        product = products.get(str(row.get("pizza")))
        try:
            rating = int(row.get("stars") or 0)
        except (TypeError, ValueError):
            rating = 0
        decorated.append(
            {
                "id": str(row.get("id") or ""),
                "rating": rating,
                "comment": str(row.get("comment") or "").strip(),
                "author_display": (
                    local_review.author_display if local_review is not None else GUEST_LABEL
                ),
                "created_at": (
                    local_review.created_at if local_review is not None else _created_at(row)
                ),
                "product_name": product.name if product is not None else "",
                "product_url": product.get_absolute_url() if product is not None else "",
            }
        )

    decorated.sort(
        key=lambda item: item["created_at"].timestamp() if item["created_at"] else 0.0,
        reverse=True,
    )
    return decorated


def visible_reviews() -> list[dict[str, Any]]:
    """Every review, newest first (public page). Raises ``ApiError`` when offline."""
    return _decorate(remote_rows())


def product_reviews(product: Product) -> list[dict[str, Any]]:
    """Reviews of a single product (empty when it has no API link)."""
    if product.api_id is None:
        return []
    return _decorate(remote_rows(product.api_id))


def rating_summary(reviews: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Count and (future) average for a list of reviews already loaded.

    TODO(reviews-media): define how the average is computed (rounded, weighted
    or recalculated by the API) and fill ``average``. Until then the count is
    the only value templates may show.
    """
    return {"average": None, "count": len(reviews)}


def create_review(
    *, order_item: Any, author: Any, rating: int, comment: str
) -> Review:
    """``POST /reviews/`` and keep the local record that owns the authorship.

    The local row is what guarantees "one review per purchased item", so it is
    written only after the API accepted the review.
    """
    product = order_item.product
    if product.api_id is None:
        raise ApiError("Este produto não está vinculado à API e não pode ser avaliado.")

    payload = {
        "pizza": str(product.api_id),
        "stars": int(rating),
        "comment": str(comment).strip(),
    }
    remote = api_client.post("reviews/", json=payload)

    api_id: str | None = None
    if isinstance(remote, dict) and remote.get("id") is not None:
        api_id = str(remote["id"])[:64]

    return Review.objects.create(
        order_item=order_item,
        product=product,
        author=author,
        rating=int(rating),
        comment=str(comment).strip(),
        api_id=api_id,
    )
