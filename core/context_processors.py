"""Template context shared by every page."""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.http import HttpRequest
from django.utils import timezone


def site(request: HttpRequest) -> dict[str, Any]:
    """Branding and small global values."""
    return {
        "site_name": settings.SITE_NAME,
        "site_tagline": settings.SITE_TAGLINE,
        "current_year": timezone.localdate().year,
        "api_base_url": settings.PIZZA_API_BASE_URL,
    }


def cart(request: HttpRequest) -> dict[str, int]:
    """Total quantity of items in the session cart."""
    from orders.services import cart_quantity

    session = getattr(request, "session", None)
    return {"cart_count": cart_quantity(session) if session is not None else 0}
