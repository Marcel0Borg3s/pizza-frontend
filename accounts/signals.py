"""Create a profile for every user, including ``createsuperuser`` accounts."""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from accounts.models import Profile


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def ensure_profile(sender: type[Any], instance: Any, created: bool, **kwargs: Any) -> None:
    """Keep a Profile row in sync with the auth user."""
    if created:
        Profile.objects.get_or_create(user=instance)
