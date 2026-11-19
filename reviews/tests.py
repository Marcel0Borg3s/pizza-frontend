"""Review visibility, authorship and API integration tests."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from catalog import services as catalog_services
from catalog.models import Product
from core.api import api_client
from core.testing import FakePizzaApi
from orders.models import Order, OrderItem
from reviews.models import Review


class ReviewTests(TestCase):
    def setUp(self) -> None:
        self.api = FakePizzaApi()
        self.remote_pizza = self.api.add_pizza(
            "Margherita", "49.90", "Molho, mozzarella e manjericão."
        )
        patcher = patch.object(api_client, "request", side_effect=self.api)
        patcher.start()
        self.addCleanup(patcher.stop)

        catalog_services.refresh_catalog()
        self.product = Product.objects.get()

        self.author = get_user_model().objects.create_user(
            username="joana", password="x", first_name="Joana", last_name="Prado"
        )
        self.other = get_user_model().objects.create_user(username="outro", password="x")
        self.order = Order.objects.create(
            customer=self.author,
            customer_name="Joana Prado",
            phone="19998765432",
            address="Rua das Flores",
            number="120",
            neighborhood="Cambuí",
            city="Campinas",
            total=Decimal("49.90"),
        )
        self.item = OrderItem.objects.create(
            order=self.order,
            product=self.product,
            product_name=self.product.name,
            quantity=1,
            unit_price=self.product.price,
        )

    def _mirror_review(self, remote: dict) -> Review:
        return Review.objects.create(
            order_item=self.item,
            product=self.product,
            author=self.author,
            rating=remote["stars"],
            comment=remote["comment"],
            api_id=remote["id"],
        )

    def test_anonymous_can_read_reviews_from_the_api(self) -> None:
        self.api.add_review(self.remote_pizza["id"], 5, "Massa perfeita.")
        response = self.client.get(reverse("reviews:list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Massa perfeita.")
        self.assertContains(response, "Cliente")

    def test_product_page_shows_the_local_author_of_a_mirrored_review(self) -> None:
        remote = self.api.add_review(self.remote_pizza["id"], 5, "Massa perfeita.")
        self._mirror_review(remote)
        response = self.client.get(self.product.get_absolute_url())
        self.assertContains(response, "Massa perfeita.")
        self.assertContains(response, "Joana P.")

    def test_summary_shows_the_count_without_an_average(self) -> None:
        self.api.add_review(self.remote_pizza["id"], 4, "Boa.")
        self.api.add_review(self.remote_pizza["id"], 2, "Fria.")
        response = self.client.get(reverse("reviews:list"))
        self.assertContains(response, "média de notas em breve")
        self.assertEqual(response.context["summary"]["count"], 2)
        self.assertIsNone(response.context["summary"]["average"])

    def test_reviews_page_survives_api_failure(self) -> None:
        self.api.offline = True
        response = self.client.get(reverse("reviews:list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Não foi possível carregar as avaliações")

    def test_anonymous_cannot_create_review(self) -> None:
        response = self.client.post(
            reverse("reviews:create", args=[self.item.pk]),
            {"rating": 5, "comment": "Muito boa."},
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Review.objects.exists())

    def test_customer_reviews_own_item_through_the_api(self) -> None:
        self.client.force_login(self.author)
        response = self.client.post(
            reverse("reviews:create", args=[self.item.pk]),
            {"rating": 5, "comment": "Massa perfeita, entrega rápida."},
            follow=True,
        )
        self.assertRedirects(response, self.product.get_absolute_url())
        review = Review.objects.get()
        self.assertEqual(review.author, self.author)
        self.assertEqual(review.product, self.product)
        self.assertEqual(review.order_item, self.item)
        self.assertIsNotNone(review.api_id)
        self.assertEqual(len(self.api.reviews), 1)
        self.assertEqual(next(iter(self.api.reviews.values()))["stars"], 5)

    def test_cannot_review_someone_elses_item(self) -> None:
        self.client.force_login(self.other)
        response = self.client.post(
            reverse("reviews:create", args=[self.item.pk]),
            {"rating": 1, "comment": "Não comprei."},
        )
        self.assertEqual(response.status_code, 404)
        self.assertFalse(Review.objects.exists())

    def test_cannot_review_the_same_item_twice(self) -> None:
        remote = self.api.add_review(self.remote_pizza["id"], 4, "Boa.")
        self._mirror_review(remote)
        self.client.force_login(self.author)
        response = self.client.post(
            reverse("reviews:create", args=[self.item.pk]),
            {"rating": 2, "comment": "Segunda tentativa."},
        )
        self.assertRedirects(response, self.product.get_absolute_url())
        self.assertEqual(Review.objects.count(), 1)
        self.assertEqual(len(self.api.reviews), 1)

    def test_rating_must_be_between_one_and_five(self) -> None:
        self.client.force_login(self.author)
        response = self.client.post(
            reverse("reviews:create", args=[self.item.pk]),
            {"rating": 9, "comment": "Nota inválida."},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Review.objects.exists())

    def test_api_failure_keeps_the_review_out_of_the_database(self) -> None:
        self.api.offline = True
        self.client.force_login(self.author)
        response = self.client.post(
            reverse("reviews:create", args=[self.item.pk]),
            {"rating": 5, "comment": "Massa perfeita."},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Não foi possível conectar à API")
        self.assertFalse(Review.objects.exists())
