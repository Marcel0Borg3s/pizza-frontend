"""Catalog views: the menu is mirrored from ``GET /pizzas/``."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from catalog.models import Product
from core.api import api_client
from core.testing import FakePizzaApi


class CatalogViewTests(TestCase):
    def setUp(self) -> None:
        self.api = FakePizzaApi()
        self.margherita = self.api.add_pizza(
            "Margherita", "49.90", "Molho, mozzarella e manjericão."
        )
        self.calabresa = self.api.add_pizza("Calabresa", "54.90", "Calabresa e cebola.")
        patcher = patch.object(api_client, "request", side_effect=self.api)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_home_mirrors_the_api_menu(self) -> None:
        response = self.client.get(reverse("catalog:home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Margherita")
        self.assertContains(response, "R$ 49,90")
        self.assertEqual(Product.objects.count(), 2)
        self.assertIn(("GET", "pizzas/"), self.api.calls)

    def test_mirror_keeps_the_api_price(self) -> None:
        self.client.get(reverse("catalog:home"))
        product = Product.objects.get(api_id=self.calabresa["id"])
        self.assertEqual(product.price, Decimal("54.90"))

    def test_search_filters_by_name(self) -> None:
        response = self.client.get(reverse("catalog:home"), {"q": "cala"})
        self.assertContains(response, "Calabresa")
        self.assertNotContains(response, "Margherita")

    def test_search_filters_by_description(self) -> None:
        response = self.client.get(reverse("catalog:home"), {"q": "manjericão"})
        self.assertContains(response, "Margherita")
        self.assertNotContains(response, "Calabresa")

    def test_detail_shows_product_and_reviews_area(self) -> None:
        self.client.get(reverse("catalog:home"))
        product = Product.objects.get(api_id=self.margherita["id"])
        response = self.client.get(product.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Avaliações deste produto")
        self.assertContains(response, "Margherita")

    def test_pizza_removed_from_the_api_leaves_the_menu(self) -> None:
        self.client.get(reverse("catalog:home"))
        del self.api.pizzas[self.margherita["id"]]
        response = self.client.get(reverse("catalog:home"))
        self.assertNotContains(response, "Margherita")
        product = Product.objects.get(api_id=self.margherita["id"])
        self.assertFalse(product.is_available)

    def test_page_still_renders_when_the_api_is_offline(self) -> None:
        self.client.get(reverse("catalog:home"))
        self.api.offline = True
        response = self.client.get(reverse("catalog:home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Margherita")
        self.assertContains(response, "Não foi possível atualizar o cardápio")

    def test_slug_is_generated_from_the_flavor(self) -> None:
        self.client.get(reverse("catalog:home"))
        product = Product.objects.get(api_id=self.margherita["id"])
        self.assertEqual(product.slug, "margherita")

    def test_legacy_local_row_is_adopted_instead_of_duplicated(self) -> None:
        legacy = Product.objects.create(
            name="Margherita", description="Receita antiga.", price=Decimal("39.90")
        )
        self.client.get(reverse("catalog:home"))
        legacy.refresh_from_db()
        self.assertEqual(str(legacy.api_id), self.margherita["id"])
        self.assertEqual(Product.objects.filter(name="Margherita").count(), 1)


class SeedCatalogTests(TestCase):
    def setUp(self) -> None:
        self.api = FakePizzaApi()
        patcher = patch.object(api_client, "request", side_effect=self.api)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_seed_is_idempotent_in_the_api(self) -> None:
        call_command("seed_catalog", verbosity=0)
        first_count = len(self.api.pizzas)
        call_command("seed_catalog", verbosity=0)
        self.assertEqual(len(self.api.pizzas), first_count)
        self.assertGreaterEqual(first_count, 9)
        self.assertEqual(Product.objects.count(), first_count)
