"""Create or update the owner account (staff, optional superuser)."""

from __future__ import annotations

import os
from typing import Any

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Cria (ou atualiza) o usuário dono da pizzaria com acesso ao painel."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--username",
            default=os.getenv("DEMO_OWNER_USERNAME", "dono"),
            help="Apelido do dono (padrão: variável DEMO_OWNER_USERNAME ou 'dono').",
        )
        parser.add_argument(
            "--password",
            default=os.getenv("DEMO_OWNER_PASSWORD", ""),
            help="Senha do dono (padrão: variável DEMO_OWNER_PASSWORD).",
        )
        parser.add_argument("--email", default="", help="Email opcional.")
        parser.add_argument(
            "--superuser",
            action="store_true",
            help="Também concede acesso ao /admin/ do Django.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        username: str = options["username"].strip()
        password: str = options["password"]
        if not username:
            raise CommandError("Informe um apelido com --username.")
        if not password:
            raise CommandError(
                "Informe uma senha com --password ou defina DEMO_OWNER_PASSWORD no .env."
            )

        user_model = get_user_model()
        user, created = user_model.objects.get_or_create(
            username=username,
            defaults={"email": options["email"]},
        )
        user.is_staff = True
        if options["superuser"]:
            user.is_superuser = True
        if options["email"]:
            user.email = options["email"]
        user.set_password(password)
        user.save()

        action = "criado" if created else "atualizado"
        self.stdout.write(
            self.style.SUCCESS(
                f'Dono "{username}" {action}. Acesse /painel/ para gerenciar a loja.'
            )
        )
