"""Registration, login and profile tests."""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.models import Profile
from accounts.services import register_customer
from core.api import ApiError

VALID_FORM: dict[str, str] = {
    "name": "Joana Prado",
    "nickname": "Joana",
    "phone": "(19) 99876-5432",
    "address": "Rua das Flores",
    "number": "120",
    "neighborhood": "Cambuí",
    "city": "Campinas",
    "password": "MassaArtesanal2026",
    "password_confirm": "MassaArtesanal2026",
}

CLIENT_PAYLOAD: dict[str, Any] = {
    "id": str(uuid.uuid4()),
    "name": "Joana Prado",
    "nickname": "joana",
    "phone": "19998765432",
    "address": "Rua das Flores",
    "number": "120",
    "neighborhood": "Cambuí",
    "city": "Campinas",
}


class RegisterServiceTests(TestCase):
    @patch("accounts.services.create_client", return_value=CLIENT_PAYLOAD)
    def test_creates_user_and_profile_linked_to_api(self, create_client: Any) -> None:
        user = register_customer({**VALID_FORM, "nickname": "joana"})
        self.assertEqual(user.username, "joana")
        self.assertTrue(user.check_password(VALID_FORM["password"]))
        profile = Profile.objects.get(user=user)
        self.assertEqual(str(profile.client_id), CLIENT_PAYLOAD["id"])
        self.assertEqual(profile.nickname, "joana")
        create_client.assert_called_once()


class RegisterViewTests(TestCase):
    @patch(
        "catalog.services.refresh_catalog",
        return_value={"total": 0, "created": 0, "updated": 0, "hidden": 0},
    )
    @patch("accounts.services.create_client", return_value={**CLIENT_PAYLOAD, "nickname": "joana"})
    def test_register_creates_remote_client_and_logs_in(
        self, create_client: Any, refresh_catalog: Any
    ) -> None:
        response = self.client.post(reverse("accounts:register"), data=VALID_FORM, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["user"].is_authenticated)
        self.assertEqual(get_user_model().objects.count(), 1)
        payload = create_client.call_args.args[0]
        self.assertEqual(payload["nickname"], "joana")
        self.assertEqual(payload["phone"], "19998765432")

    @patch(
        "accounts.services.create_client",
        side_effect=ApiError(
            "client with this nickname already exists.",
            status_code=400,
            details={"nickname": ["client with this nickname already exists."]},
        ),
    )
    def test_api_validation_error_is_shown_on_the_field(self, create_client: Any) -> None:
        response = self.client.post(reverse("accounts:register"), data=VALID_FORM)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "API: client with this nickname already exists.")
        self.assertEqual(get_user_model().objects.count(), 0)

    @patch("accounts.services.create_client", side_effect=ApiError("API fora do ar"))
    def test_offline_api_keeps_form_usable(self, create_client: Any) -> None:
        response = self.client.post(reverse("accounts:register"), data=VALID_FORM)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "API fora do ar")
        self.assertEqual(get_user_model().objects.count(), 0)

    def test_duplicate_local_nickname_is_rejected_before_calling_api(self) -> None:
        get_user_model().objects.create_user(username="joana", password="x")
        with patch("accounts.services.create_client") as create_client:
            response = self.client.post(reverse("accounts:register"), data=VALID_FORM)
        self.assertEqual(response.status_code, 200)
        create_client.assert_not_called()

    def test_password_mismatch(self) -> None:
        data = {**VALID_FORM, "password_confirm": "outra-senha-123"}
        response = self.client.post(reverse("accounts:register"), data=data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "As senhas não coincidem.")


class LoginTests(TestCase):
    def setUp(self) -> None:
        self.user = get_user_model().objects.create_user(
            username="joana", password="MassaArtesanal2026"
        )

    @patch(
        "catalog.services.refresh_catalog",
        return_value={"total": 0, "created": 0, "updated": 0, "hidden": 0},
    )
    def test_login_with_registered_credentials(self, refresh_catalog: Any) -> None:
        response = self.client.post(
            reverse("accounts:login"),
            data={"username": "joana", "password": "MassaArtesanal2026"},
        )
        self.assertRedirects(response, reverse("catalog:home"))
        self.assertTrue(self.client.session["_auth_user_id"])

    def test_logout_requires_post(self) -> None:
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("accounts:logout")).status_code, 405)


class ProfileViewTests(TestCase):
    def setUp(self) -> None:
        self.user = get_user_model().objects.create_user(username="joana", password="x")
        Profile.objects.update_or_create(
            user=self.user, defaults={"client_id": uuid.uuid4(), "nickname": "joana"}
        )

    def test_anonymous_is_redirected(self) -> None:
        response = self.client.get(reverse("accounts:profile"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response.url)

    @patch("accounts.services.fetch_client", return_value=CLIENT_PAYLOAD)
    def test_profile_shows_client_from_api(self, fetch_client: Any) -> None:
        self.client.force_login(self.user)
        response = self.client.get(reverse("accounts:profile"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Rua das Flores")
        self.assertContains(response, "sincronizado")
        fetch_client.assert_called_once()

    @patch("accounts.services.fetch_client", side_effect=ApiError("sem conexão"))
    def test_profile_survives_api_failure(self, fetch_client: Any) -> None:
        self.client.force_login(self.user)
        response = self.client.get(reverse("accounts:profile"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "API indisponível agora")
