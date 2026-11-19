"""In-memory stand-in for the pizza_drf API, used by the test suite.

The tests never touch the network: they patch ``api_client.request`` with a
``FakePizzaApi`` instance and assert on ``fake.calls`` / the stored rows.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

from core.api import ApiError

BASE_TIME = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


def _price(value: Any) -> str:
    try:
        return f"{Decimal(str(value)).quantize(Decimal('0.01')):.2f}"
    except (InvalidOperation, ValueError, TypeError):
        return "0.00"


class FakePizzaApi:
    """Route ``api_client.request`` calls to in-memory pizzas and reviews."""

    def __init__(self, *, offline: bool = False) -> None:
        self.offline = offline
        self.pizzas: dict[str, dict[str, Any]] = {}
        self.reviews: dict[str, dict[str, Any]] = {}
        self.calls: list[tuple[str, str]] = []
        self._clock = BASE_TIME

    # -- fixtures ----------------------------------------------------------

    def _tick(self) -> datetime:
        self._clock += timedelta(minutes=1)
        return self._clock

    def add_pizza(
        self,
        flavor: str,
        price: Any = "49.90",
        description: str = "",
        pizza_id: str | None = None,
    ) -> dict[str, Any]:
        api_id = pizza_id or str(uuid.uuid4())
        stamp = self._tick().isoformat()
        row = {
            "id": api_id,
            "flavor": flavor,
            "description": description,
            "price": _price(price),
            "created_at": stamp,
            "updated_at": stamp,
        }
        self.pizzas[api_id] = row
        return row

    def add_review(
        self,
        pizza_id: str,
        stars: int,
        comment: str = "",
        review_id: str | None = None,
    ) -> dict[str, Any]:
        api_id = review_id or str(uuid.uuid4())
        row = {
            "id": api_id,
            "pizza": pizza_id,
            "stars": int(stars),
            "comment": comment,
            "created_at": self._tick().isoformat(),
        }
        self.reviews[api_id] = row
        return row

    # -- request handling --------------------------------------------------

    def __call__(
        self,
        method: str,
        path: str,
        *,
        params: Any = None,
        json: Any = None,
    ) -> Any:
        method = method.upper()
        self.calls.append((method, path.rstrip("/") + "/"))
        if self.offline:
            raise ApiError("Não foi possível conectar à API.")

        segments = [segment for segment in path.strip("/").split("/") if segment]
        if not segments:
            raise ApiError("Rota vazia.", status_code=404)

        handlers = {"pizzas": self._pizzas, "reviews": self._reviews, "clients": self._clients}
        handler = handlers.get(segments[0])
        if handler is None:
            raise ApiError("Rota desconhecida.", status_code=404)
        return handler(method, segments[1:], params=params, json=json)

    def _pizzas(
        self, method: str, rest: list[str], *, params: Any = None, json: Any = None
    ) -> Any:
        if not rest:
            if method == "GET":
                return [dict(row) for row in self.pizzas.values()]
            if method == "POST":
                payload = dict(json or {})
                if not str(payload.get("flavor", "")).strip():
                    raise ApiError(
                        "Sabor obrigatório.",
                        status_code=400,
                        details={"flavor": ["Este campo é obrigatório."]},
                    )
                return self.add_pizza(
                    str(payload["flavor"]),
                    payload.get("price", "0.00"),
                    str(payload.get("description") or ""),
                )
            raise ApiError("Método não permitido.", status_code=405)

        pizza_id = rest[0]
        row = self.pizzas.get(pizza_id)
        if row is None:
            raise ApiError("Não encontrado.", status_code=404)
        if method in {"GET", "HEAD"}:
            return dict(row)
        if method in {"PATCH", "PUT"}:
            for field in ("flavor", "description", "price"):
                if field in (json or {}):
                    row[field] = (
                        _price(json[field]) if field == "price" else str(json[field])
                    )
            row["updated_at"] = self._tick().isoformat()
            return dict(row)
        if method == "DELETE":
            if any(review["pizza"] == pizza_id for review in self.reviews.values()):
                raise ApiError(
                    "Esta pizza já possui avaliações e não pode ser excluída.",
                    status_code=409,
                )
            del self.pizzas[pizza_id]
            return None
        raise ApiError("Método não permitido.", status_code=405)

    def _reviews(
        self, method: str, rest: list[str], *, params: Any = None, json: Any = None
    ) -> Any:
        if rest:
            raise ApiError("Não encontrado.", status_code=404)
        if method == "GET":
            pizza = (params or {}).get("pizza")
            rows = [
                dict(row)
                for row in self.reviews.values()
                if pizza is None or row["pizza"] == pizza
            ]
            return sorted(rows, key=lambda item: item["created_at"], reverse=True)
        if method == "POST":
            payload = dict(json or {})
            if payload.get("pizza") not in self.pizzas:
                raise ApiError(
                    "Pizza inválida.",
                    status_code=400,
                    details={"pizza": ["Pizza inexistente."]},
                )
            try:
                stars = int(payload.get("stars", 0))
            except (TypeError, ValueError):
                stars = 0
            if not 1 <= stars <= 5:
                raise ApiError(
                    "Nota inválida.",
                    status_code=400,
                    details={"stars": ["A nota deve ficar entre 1 e 5."]},
                )
            return self.add_review(
                str(payload["pizza"]), stars, str(payload.get("comment") or "")
            )
        raise ApiError("Método não permitido.", status_code=405)

    @staticmethod
    def _clients(
        method: str, rest: list[str], *, params: Any = None, json: Any = None
    ) -> Any:
        if method == "GET":
            return []
        raise ApiError("Método não permitido.", status_code=405)
