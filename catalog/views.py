"""Catalog views: menu with search and product details.

Every page refreshes the mirror from ``GET /pizzas/`` first. When the API is
offline the page still renders with the last mirrored menu plus a warning, so a
restart of pizza_drf never takes the whole store down.
"""

from __future__ import annotations

from typing import Any

from django.http import Http404
from django.views.generic import DetailView, ListView

from catalog import services
from catalog.models import Product
from core.api import ApiError
from reviews.services import product_reviews, rating_summary


class CatalogSyncMixin:
    """Pull ``GET /pizzas/`` into the local mirror before rendering."""

    api_error: str | None = None

    def dispatch(self, request: Any, *args: Any, **kwargs: Any) -> Any:
        try:
            services.refresh_catalog()
        except ApiError as exc:
            self.api_error = exc.message
        return super().dispatch(request, *args, **kwargs)


class ProductListView(CatalogSyncMixin, ListView):
    """Public menu, searchable and filterable by category."""

    model = Product
    template_name = "catalog/home.html"
    context_object_name = "products"
    paginate_by = 12

    def get_queryset(self) -> Any:
        self.search = self.request.GET.get("q", "").strip()[:80]
        self.category = self.request.GET.get("categoria", "").strip()
        return services.list_products(search=self.search, category=self.category)

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["search"] = self.search
        context["active_category"] = self.category
        context["categories"] = services.categories()
        context["api_error"] = self.api_error
        return context


class ProductDetailView(CatalogSyncMixin, DetailView):
    """Product page with its public reviews, read from ``GET /reviews/``."""

    model = Product
    template_name = "catalog/detail.html"
    context_object_name = "product"

    def get_object(self, queryset: Any = None) -> Product:
        product = services.get_product(self.kwargs["slug"])
        if product is None:
            raise Http404("Produto não encontrado.")
        return product

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        try:
            reviews = product_reviews(self.object)
            self.reviews_error = None
        except ApiError as exc:
            reviews = []
            self.reviews_error = exc.message
        context["reviews"] = reviews[:10]
        context["rating"] = rating_summary(reviews)
        context["api_error"] = self.reviews_error or self.api_error
        return context
