"""Local account models.

The customer record itself lives in the pizza_drf API (``/clients/``). Here we
keep only what the frontend needs: the Django user used for login and the UUID
returned by the API, so orders and reviews can be tied to a real customer.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models


class Profile(models.Model):
    """Extra data for an authenticated user."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
        verbose_name="usuário",
    )
    client_id = models.UUIDField(
        "ID do cliente na API",
        null=True,
        blank=True,
        unique=True,
        editable=False,
    )
    nickname = models.CharField("apelido", max_length=30, blank=True)
    created_at = models.DateTimeField("criado em", auto_now_add=True)
    updated_at = models.DateTimeField("atualizado em", auto_now=True)

    class Meta:
        verbose_name = "perfil"
        verbose_name_plural = "perfis"
        ordering = ["user__username"]

    def __str__(self) -> str:
        return self.nickname or self.user.get_username()

    @property
    def has_api_link(self) -> bool:
        """True when this account is backed by a client in the API."""
        return self.client_id is not None
