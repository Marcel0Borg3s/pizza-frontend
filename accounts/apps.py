"""Accounts app: local login plus the link to the client created in the API."""

from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "accounts"
    verbose_name = "Contas"

    def ready(self) -> None:
        from accounts import signals  # noqa: F401
