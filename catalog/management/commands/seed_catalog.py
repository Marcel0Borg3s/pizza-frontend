"""Seed the demo menu in the pizza_drf API (idempotent).

The menu belongs to the API, so this command talks to ``/pizzas/``: flavors that
already exist are only updated (description and price), the missing ones are
created. Run it with pizza_drf up; afterwards the local mirror is refreshed.
"""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand, CommandError

from catalog import api as pizza_api
from catalog import services
from core.api import ApiError

MENU: list[dict[str, str]] = [
    {
        "flavor": "Margherita",
        "price": "49.90",
        "description": (
            "Molho de tomate italiano, mozzarella de búfala, manjericão fresco e azeite."
        ),
    },
    {
        "flavor": "Calabresa Defumada",
        "price": "54.90",
        "description": "Calabresa artesanal defumada, cebola roxa e orégano.",
    },
    {
        "flavor": "Portuguesa da Casa",
        "price": "56.90",
        "description": "Presunto, ovos, cebola, azeitona preta e ervilha.",
    },
    {
        "flavor": "Quatro Queijos",
        "price": "62.90",
        "description": "Mozzarella, gorgonzola, parmesão e catupiry.",
    },
    {
        "flavor": "Pepperoni Picante",
        "price": "64.90",
        "description": "Pepperoni, flocos de pimenta calabresa e mel picante.",
    },
    {
        "flavor": "Trufa e Funghi",
        "price": "74.90",
        "description": "Creme de trufa, cogumelos paris e mozzarella.",
    },
    {
        "flavor": "Vegetariana do Horto",
        "price": "58.90",
        "description": "Abobrinha, berinjela, tomate confit e pesto de manjericão.",
    },
    {
        "flavor": "Margherita Vegana",
        "price": "60.90",
        "description": "Mozzarella vegetal de castanha, tomate e manjericão.",
    },
    {
        "flavor": "Chocolate com Morango",
        "price": "46.90",
        "description": "Chocolate meio amargo, morangos frescos e açúcar de confeiteiro.",
    },
]


class Command(BaseCommand):
    help = "Cria ou atualiza o cardápio de demonstração na API pizza_drf."

    def handle(self, *args: Any, **options: Any) -> None:
        try:
            remote = {
                str(row.get("flavor", "")).strip().lower(): row
                for row in pizza_api.list_pizzas()
            }
        except ApiError as exc:
            raise CommandError(
                f"A API não respondeu ({exc.message}). Suba o pizza_drf antes."
            ) from exc

        created = updated = 0
        for item in MENU:
            payload = pizza_api.build_payload(
                flavor=item["flavor"],
                description=item["description"],
                price=item["price"],
            )
            existing = remote.get(payload["flavor"].lower())
            try:
                if existing is None:
                    pizza_api.create_pizza(payload)
                    created += 1
                else:
                    pizza_api.update_pizza(str(existing["id"]), payload)
                    updated += 1
            except ApiError as exc:
                raise CommandError(f"Falha ao gravar “{payload['flavor']}”: {exc.message}") from exc

        try:
            result = services.refresh_catalog()
        except ApiError as exc:
            raise CommandError(f"Cardápio gravado, mas o espelho falhou: {exc.message}") from exc

        self.stdout.write(
            self.style.SUCCESS(
                f"Cardápio na API: {created} criado(s), {updated} atualizado(s). "
                f"Espelho local com {result['total']} pizza(s)."
            )
        )
