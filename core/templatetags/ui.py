"""Formatting helpers for Brazilian currency, phone numbers and labels."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django import template
from django.utils.html import format_html
from django.utils.safestring import SafeString, mark_safe

register = template.Library()


@register.filter
def brl(value: Decimal | float | int | str | None) -> str:
    """Format a number as Brazilian currency: ``R$ 1.234,56``."""
    if value in (None, ""):
        return "R$ 0,00"
    try:
        amount = Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return "R$ 0,00"
    formatted = f"{amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {formatted}"


@register.filter
def phone(value: str | None) -> str:
    """Format a Brazilian phone number: ``(19) 91234-5678``."""
    digits = "".join(char for char in (value or "") if char.isdigit())
    if len(digits) == 11:
        return f"({digits[:2]}) {digits[2:7]}-{digits[7:]}"
    if len(digits) == 10:
        return f"({digits[:2]}) {digits[2:6]}-{digits[6:]}"
    return value or ""


@register.filter
def initials(value: str | None) -> str:
    """Return up to two initials from a name."""
    parts = [part for part in (value or "").split() if part]
    return "".join(part[0].upper() for part in parts[:2]) or "?"


@register.simple_tag
def stars(rating: int) -> SafeString:
    """Render a 5 star rating as text, accessible to screen readers."""
    rating = max(0, min(5, int(rating or 0)))
    filled = "★" * rating
    empty = "☆" * (5 - rating)
    return format_html(
        '<span class="text-amber-500" aria-label="{} de 5 estrelas">{}{}</span>',
        rating,
        mark_safe(filled),
        mark_safe(empty),
    )
