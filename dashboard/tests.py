"""Owner panel permissions, pizza CRUD against the API, orders and clients."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from catalog.models import Product
from core.api import ApiError, api_client
from core.testing import FakePizzaApi
from orders.models import Order

CLIENT = {
    "id": "2f1a0f0e-0000-4000-8000-000000000001",
    "name": "Joana Prado",
    "nickname": "joana",
    "phone": "19998765432",
    "address": "Rua das Flores",
    "number": "120",
    "neighborhood": "Cambuí",
    "city": "Campinas",
    "created_at": "2026-01-10T10:00:00-03:00",
    "updated_at": "2026-01-10T10:00:00-03:00",
}

PIZZA_FORM = {
    "flavor": "Napolitana",
    "price": "59.90",
    "description": "Tomate, mozzarella e alho.",
}


class ApiTestCase(TestCase):
    """Every test runs against an in-memory pizza_drf, never the network."""

    def setUp(self) -> None:
        super().setUp()
        self.api = FakePizzaApi()
        patcher = patch.object(api_client, "request", side_effect=self.api)
        patcher.start()
        self.addCleanup(patcher.stop)


class DashboardPermissionTests(ApiTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.customer = get_user_model().objects.create_user(username="cliente", password="x")
        self.owner = get_user_model().objects.create_user(
            username="dono", password="x", is_staff=True
        )

    def test_anonymous_is_redirected_to_login(self) -> None:
        response = self.client.get(reverse("dashboard:index"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response.url)

    def test_customer_gets_403(self) -> None:
        self.client.force_login(self.customer)
        response = self.client.get(reverse("dashboard:index"))
        self.assertEqual(response.status_code, 403)

    @patch("dashboard.views.list_clients", return_value=[CLIENT])
    def test_owner_sees_panel(self, list_clients: object) -> None:
        self.api.add_pizza("Margherita", "49.90")
        self.client.force_login(self.owner)
        response = self.client.get(reverse("dashboard:index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Painel do dono")
        self.assertContains(response, "online")
        self.assertContains(response, "Pizzas na API")

    @patch("dashboard.views.list_clients", side_effect=ApiError("sem conexão"))
    def test_panel_reports_api_failure(self, list_clients: object) -> None:
        self.api.offline = True
        self.client.force_login(self.owner)
        response = self.client.get(reverse("dashboard:index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "sem conexão")


class DashboardCatalogTests(ApiTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.owner = get_user_model().objects.create_user(
            username="dono", password="x", is_staff=True
        )
        self.client.force_login(self.owner)

    def test_create_pizza_in_the_api(self) -> None:
        response = self.client.post(reverse("dashboard:product_create"), data=PIZZA_FORM)
        self.assertRedirects(response, reverse("dashboard:product_list"))

        self.assertEqual(len(self.api.pizzas), 1)
        remote = next(iter(self.api.pizzas.values()))
        self.assertEqual(remote["flavor"], "Napolitana")
        self.assertEqual(remote["price"], "59.90")

        mirror = Product.objects.get()
        self.assertEqual(str(mirror.api_id), remote["id"])
        self.assertEqual(mirror.name, "Napolitana")
        self.assertEqual(mirror.price, Decimal("59.90"))

    def test_update_flavor_and_price_in_the_api(self) -> None:
        remote = self.api.add_pizza("Margherita", "49.90", "Molho e mozzarella.")
        response = self.client.post(
            reverse("dashboard:product_update", args=[remote["id"]]),
            data={**PIZZA_FORM, "flavor": "Margherita", "price": "52.50"},
        )
        self.assertRedirects(response, reverse("dashboard:product_list"))

        self.assertEqual(self.api.pizzas[remote["id"]]["price"], "52.50")
        mirror = Product.objects.get(api_id=remote["id"])
        self.assertEqual(mirror.name, "Margherita")
        self.assertEqual(mirror.price, Decimal("52.50"))

    def test_update_form_is_prefilled_from_the_api(self) -> None:
        remote = self.api.add_pizza("Margherita", "49.90", "Molho e mozzarella.")
        response = self.client.get(reverse("dashboard:product_update", args=[remote["id"]]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "PATCH /pizzas/")
        self.assertContains(response, "Margherita")

    def test_price_must_be_positive(self) -> None:
        response = self.client.post(
            reverse("dashboard:product_create"), data={**PIZZA_FORM, "price": "0"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(self.api.pizzas)
        self.assertFalse(Product.objects.exists())

    def test_delete_pizza_in_the_api(self) -> None:
        remote = self.api.add_pizza("Margherita", "49.90", "Molho e mozzarella.")
        self.client.get(reverse("dashboard:product_list"))

        response = self.client.post(reverse("dashboard:product_delete", args=[remote["id"]]))
        self.assertRedirects(response, reverse("dashboard:product_list"))

        self.assertNotIn(remote["id"], self.api.pizzas)
        mirror = Product.objects.get()
        self.assertIsNone(mirror.api_id)
        self.assertFalse(mirror.is_available)

    def test_delete_is_refused_when_the_pizza_has_reviews(self) -> None:
        remote = self.api.add_pizza("Margherita", "49.90", "Molho e mozzarella.")
        self.api.add_review(remote["id"], 5, "Massa perfeita.")
        self.client.get(reverse("dashboard:product_list"))

        response = self.client.post(
            reverse("dashboard:product_delete", args=[remote["id"]]), follow=True
        )
        self.assertRedirects(response, reverse("dashboard:product_list"))
        self.assertContains(response, "já possui avaliações")
        self.assertIn(remote["id"], self.api.pizzas)
        self.assertIsNotNone(Product.objects.get().api_id)

    def test_customer_cannot_create_product(self) -> None:
        customer = get_user_model().objects.create_user(username="cliente", password="x")
        self.client.force_login(customer)
        response = self.client.post(reverse("dashboard:product_create"), data=PIZZA_FORM)
        self.assertEqual(response.status_code, 403)
        self.assertFalse(self.api.pizzas)
        self.assertFalse(Product.objects.exists())


class DashboardOrderTests(ApiTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.owner = get_user_model().objects.create_user(
            username="dono", password="x", is_staff=True
        )
        self.customer = get_user_model().objects.create_user(username="cliente", password="x")
        self.order = Order.objects.create(
            customer=self.customer,
            customer_name="Joana Prado",
            phone="19998765432",
            address="Rua das Flores",
            number="120",
            neighborhood="Cambuí",
            city="Campinas",
            total=Decimal("49.90"),
        )

    def test_owner_updates_order_status(self) -> None:
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("dashboard:order_status", args=[self.order.pk]),
            {"status": Order.Status.CONFIRMED},
        )
        self.assertRedirects(response, reverse("dashboard:order_list"))
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.CONFIRMED)

    def test_invalid_status_is_rejected(self) -> None:
        self.client.force_login(self.owner)
        self.client.post(
            reverse("dashboard:order_status", args=[self.order.pk]), {"status": "hacked"}
        )
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PENDING)

    def test_customer_cannot_change_status(self) -> None:
        self.client.force_login(self.customer)
        response = self.client.post(
            reverse("dashboard:order_status", args=[self.order.pk]),
            {"status": Order.Status.DELIVERED},
        )
        self.assertEqual(response.status_code, 403)


class DashboardClientTests(ApiTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.owner = get_user_model().objects.create_user(
            username="dono", password="x", is_staff=True
        )
        self.client.force_login(self.owner)

    @patch("dashboard.views.list_clients", return_value=[CLIENT])
    def test_client_list_comes_from_api(self, list_clients: object) -> None:
        response = self.client.get(reverse("dashboard:client_list"))
        self.assertContains(response, "Joana Prado")
        self.assertContains(response, "fonte: pizza_drf")

    @patch("dashboard.views.list_clients", return_value=[CLIENT])
    def test_client_search_filters_in_memory(self, list_clients: object) -> None:
        response = self.client.get(reverse("dashboard:client_list"), {"q": "zzz"})
        self.assertNotContains(response, "Joana Prado")

    @patch("dashboard.views.list_clients", side_effect=ApiError("timeout na API"))
    def test_client_list_handles_api_error(self, list_clients: object) -> None:
        response = self.client.get(reverse("dashboard:client_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "timeout na API")

    @patch("dashboard.views.fetch_client", return_value=CLIENT)
    def test_client_detail_reads_one_client(self, fetch_client: object) -> None:
        response = self.client.get(reverse("dashboard:client_detail", args=[CLIENT["id"]]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Joana Prado")
        self.assertContains(response, "GET /clients/")

    @patch("dashboard.views.fetch_client", side_effect=ApiError("cliente sumiu"))
    def test_client_detail_handles_api_error(self, fetch_client: object) -> None:
        response = self.client.get(reverse("dashboard:client_detail", args=[CLIENT["id"]]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "cliente sumiu")
