"""Customer registration service.

The API is the source of truth for clients: registration first posts the
customer to ``POST /clients/`` and only then creates the local login, storing
the returned UUID in ``Profile.client_id``.

If the local user cannot be created after the API call succeeds, the remote
client stays without a local account. That trade-off is acceptable for this
study project; the owner panel lists every client straight from the API.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction

from accounts.models import Profile
from core.api import ApiError
from core.api.client import api_client

CLIENT_FIELDS: tuple[str, ...] = (
    "name",
    "nickname",
    "phone",
    "address",
    "number",
    "neighborhood",
    "city",
)


def build_client_payload(data: Mapping[str, Any]) -> dict[str, str]:
    """Keep only the fields the API accepts, trimmed."""
    return {field: str(data.get(field, "")).strip() for field in CLIENT_FIELDS}


def create_client(payload: Mapping[str, str]) -> dict[str, Any]:
    """``POST /clients/`` — returns the created client."""
    response = api_client.post("clients/", json=dict(payload))
    if not isinstance(response, dict) or "id" not in response:
        raise ApiError("A API retornou um cliente inválido.")
    return response


def fetch_client(client_id: str | None) -> dict[str, Any] | None:
    """``GET /clients/<uuid>/`` — ``None`` when the API answers 404."""
    if not client_id:
        return None
    try:
        response = api_client.get(f"clients/{client_id}/")
    except ApiError as exc:
        if exc.status_code == 404:
            return None
        raise
    return response if isinstance(response, dict) else None


def list_clients() -> list[dict[str, Any]]:
    """``GET /clients/`` — supports both paginated and plain responses."""
    data = api_client.get("clients/")
    if isinstance(data, dict):
        results = data.get("results", [])
        return list(results) if isinstance(results, list) else []
    return list(data) if isinstance(data, list) else []


@transaction.atomic
def register_customer(data: Mapping[str, Any]) -> Any:
    """Create the client in the API and the local login for it.

    Raises ``ApiError`` when the API rejects the payload (for example a
    duplicated nickname); the form maps those errors back to its fields.
    """
    payload = build_client_payload(data)
    remote = create_client(payload)

    user_model = get_user_model()
    full_name = payload["name"].split()
    user = user_model.objects.create_user(
        username=payload["nickname"].lower(),
        password=str(data["password"]),
        first_name=full_name[0][:150] if full_name else "",
        last_name=" ".join(full_name[1:])[:150],
    )
    Profile.objects.update_or_create(
        user=user,
        defaults={"client_id": remote["id"], "nickname": payload["nickname"]},
    )
    return user


def sync_profile_from_api(user: Any) -> dict[str, Any] | None:
    """Return live client data for the profile page.

    The local nickname is refreshed when the API still has the client.
    """
    profile, _ = Profile.objects.get_or_create(user=user)
    if not profile.client_id:
        return None
    remote = fetch_client(str(profile.client_id))
    if remote and remote.get("nickname") and remote["nickname"] != profile.nickname:
        profile.nickname = str(remote["nickname"])[:30]
        profile.save(update_fields=["nickname", "updated_at"])
    return remote


__all__ = [
    "CLIENT_FIELDS",
    "build_client_payload",
    "create_client",
    "fetch_client",
    "list_clients",
    "register_customer",
    "settings",
    "sync_profile_from_api",
]
