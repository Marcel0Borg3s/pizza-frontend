"""Cart, checkout and order access tests."""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from catalog.models import Category, Product
from orders.models import Order
from orders.services import CART_SESSION_KEY

DELIVERY = {
    "customer_name": "Joana Prado",
    "phone": "19998765432",
    "address": "Rua das Flores",
    "number": "120",
    "neighborhood": "Cambuí",
    "city": "Campinas",
    "notes": "Sem cebola",
}


class CartTests(TestCase):
    def setUp(self) -> None:
        self.product = Product.objects.create(
            name="Margherita",
            description="Molho, mozzarella e manjericão.",
            category=Category.TRADICIONAL,
            price=Decimal("49.90"),
        )

    def test_add_to_cart_stores_quantity_in_session(self) -> None:
        response = self.client.post(
            reverse("orders:cart_add", args=[self.product.pk]),
            {"quantity": 2},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.session[CART_SESSION_KEY], {str(self.product.pk): 2})

    def test_quantity_is_capped(self) -> None:
        self.client.post(reverse("orders:cart_add", args=[self.product.pk]), {"quantity": 999})
        self.assertEqual(self.client.session[CART_SESSION_KEY], {str(self.product.pk): 20})

    def test_cart_page_shows_total(self) -> None:
        self.client.post(reverse("orders:cart_add", args=[self.product.pk]), {"quantity": 2})
        response = self.client.get(reverse("orders:cart"))
        self.assertContains(response, "R$ 99,80")

    def test_update_and_remove_lines(self) -> None:
        self.client.post(reverse("orders:cart_add", args=[self.product.pk]), {"quantity": 3})
        self.client.post(reverse("orders:cart_update", args=[self.product.pk]), {"quantity": 1})
        self.assertEqual(self.client.session[CART_SESSION_KEY], {str(self.product.pk): 1})
        self.client.post(reverse("orders:cart_remove", args=[self.product.pk]))
        self.assertEqual(self.client.session[CART_SESSION_KEY], {})

    def test_add_to_cart_requires_post(self) -> None:
        response = self.client.get(reverse("orders:cart_add", args=[self.product.pk]))
        self.assertEqual(response.status_code, 405)


class CheckoutTests(TestCase):
    def setUp(self) -> None:
        self.user = get_user_model().objects.create_user(username="joana", password="x")
        self.product = Product.objects.create(
            name="Margherita",
            description="Molho, mozzarella e manjericão.",
            category=Category.TRADICIONAL,
            price=Decimal("49.90"),
        )

    def _fill_cart(self, quantity: int = 2) -> None:
        self.client.post(reverse("orders:cart_add", args=[self.product.pk]), {"quantity": quantity})

    def test_anonymous_checkout_redirects_to_login(self) -> None:
        self._fill_cart()
        response = self.client.get(reverse("orders:checkout"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response.url)

    def test_checkout_creates_order_and_clears_cart(self) -> None:
        self.client.force_login(self.user)
        self._fill_cart()
        response = self.client.post(reverse("orders:checkout"), data=DELIVERY)
        order = Order.objects.get()
        self.assertRedirects(response, reverse("orders:detail", args=[order.pk]))
        self.assertEqual(order.total, Decimal("99.80"))
        self.assertEqual(order.items.get().quantity, 2)
        self.assertEqual(order.customer, self.user)
        self.assertEqual(self.client.session[CART_SESSION_KEY], {})

    def test_price_is_read_from_database_at_checkout(self) -> None:
        self.client.force_login(self.user)
        self._fill_cart()
        self.product.price = Decimal("59.90")
        self.product.save(update_fields=["price"])
        self.client.post(reverse("orders:checkout"), data=DELIVERY)
        order = Order.objects.get()
        self.assertEqual(order.total, Decimal("119.80"))
        self.assertEqual(order.items.get().unit_price, Decimal("59.90"))

    def test_checkout_of_unavailable_product_is_refused(self) -> None:
        self.client.force_login(self.user)
        self._fill_cart()
        self.product.is_available = False
        self.product.save(update_fields=["is_available"])
        response = self.client.post(reverse("orders:checkout"), data=DELIVERY)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Order.objects.exists())
        self.assertContains(response, "carrinho está vazio")

    @patch(
        "catalog.services.refresh_catalog",
        return_value={"total": 0, "created": 0, "updated": 0, "hidden": 0},
    )
    def test_empty_cart_redirects(self, refresh_catalog: Any) -> None:
        self.client.force_login(self.user)
        response = self.client.get(reverse("orders:checkout"))
        self.assertRedirects(response, reverse("catalog:home"))


class OrderAccessTests(TestCase):
    def setUp(self) -> None:
        self.owner = get_user_model().objects.create_user(username="joana", password="x")
        self.other = get_user_model().objects.create_user(username="outro", password="x")
        self.product = Product.objects.create(
            name="Margherita",
            description="Molho, mozzarella e manjericão.",
            category=Category.TRADICIONAL,
            price=Decimal("49.90"),
        )
        self.order = Order.objects.create(
            customer=self.owner,
            customer_name="Joana",
            phone="19998765432",
            address="Rua das Flores",
            number="120",
            neighborhood="Cambuí",
            city="Campinas",
            total=Decimal("49.90"),
        )

    def test_order_list_requires_login(self) -> None:
        response = self.client.get(reverse("orders:list"))
        self.assertEqual(response.status_code, 302)

    def test_other_customer_cannot_see_the_order(self) -> None:
        self.client.force_login(self.other)
        response = self.client.get(reverse("orders:detail", args=[self.order.pk]))
        self.assertEqual(response.status_code, 404)

    def test_owner_sees_the_order(self) -> None:
        self.client.force_login(self.owner)
        response = self.client.get(reverse("orders:detail", args=[self.order.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Pedido #")

    def test_owner_can_cancel_pending_order(self) -> None:
        self.client.force_login(self.owner)
        self.client.post(reverse("orders:cancel", args=[self.order.pk]))
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.CANCELLED)

    def test_cannot_cancel_order_already_confirmed(self) -> None:
        self.order.status = Order.Status.CONFIRMED
        self.order.save(update_fields=["status"])
        self.client.force_login(self.owner)
        self.client.post(reverse("orders:cancel", args=[self.order.pk]))
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.CONFIRMED)

    def test_other_customer_cannot_cancel(self) -> None:
        self.client.force_login(self.other)
        response = self.client.post(reverse("orders:cancel", args=[self.order.pk]))
        self.assertEqual(response.status_code, 404)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PENDING)
