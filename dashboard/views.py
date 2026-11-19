"""Owner panel: catalog management, orders, and live API inspection.

The pizza menu is edited in the API (``/pizzas/``): every write here is a
``POST``/``PATCH``/``DELETE`` on pizza_drf, followed by a mirror update. Orders
and clients keep their own flow.

Every view is protected by ``StaffRequiredMixin``: anonymous visitors are sent
to the login page and logged customers get 403.
"""

from __future__ import annotations

import time
from collections import Counter
from typing import Any

from django import forms
from django.contrib import messages
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import DetailView, FormView, ListView, TemplateView

from accounts.services import fetch_client, list_clients
from catalog import api as pizza_api
from catalog import services as catalog_services
from catalog.forms import PizzaForm
from catalog.models import Product
from core.api import ApiError, recent_calls
from core.mixins import StaffRequiredMixin
from orders.models import Order
from reviews import services as review_services

ENDPOINTS: list[dict[str, str]] = [
    {"method": "GET", "path": "/pizzas/", "use": "Cardápio, painel e espelho local"},
    {"method": "POST", "path": "/pizzas/", "use": "Nova pizza (painel do dono)"},
    {"method": "PATCH", "path": "/pizzas/<uuid>/", "use": "Alterar sabor e preço"},
    {"method": "DELETE", "path": "/pizzas/<uuid>/", "use": "Excluir pizza sem avaliações"},
    {"method": "GET", "path": "/reviews/", "use": "Lista pública (?pizza=<uuid>)"},
    {"method": "POST", "path": "/reviews/", "use": "Avaliação de item comprado"},
    {"method": "POST", "path": "/clients/", "use": "Cadastro de cliente"},
    {"method": "GET", "path": "/clients/", "use": "Lista de clientes no painel"},
    {"method": "GET", "path": "/clients/<uuid>/", "use": "Dados do cliente no perfil"},
]


def _add_api_errors(form: forms.Form, exc: ApiError) -> None:
    """Map DRF validation errors back to the form fields."""
    mapped = False
    for field, error_messages in exc.field_errors.items():
        if field in form.fields:
            form.add_error(field, error_messages)
            mapped = True
    if not mapped:
        form.add_error(None, exc.message)


class DashboardIndexView(StaffRequiredMixin, TemplateView):
    """Overview with mirror counts and a live API health check."""

    template_name = "dashboard/index.html"

    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        self.pizzas_error: str | None = None
        try:
            catalog_services.refresh_catalog()
        except ApiError as exc:
            self.pizzas_error = exc.message
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["products_count"] = Product.objects.filter(is_available=True).count()
        context["orders_count"] = Order.objects.count()
        context["pending_orders"] = Order.objects.filter(status=Order.Status.PENDING).count()

        try:
            reviews = review_services.visible_reviews()
            self.reviews_error: str | None = None
        except ApiError as exc:
            reviews = []
            self.reviews_error = exc.message
        context["reviews_count"] = len(reviews)
        context["reviews_error"] = self.reviews_error
        context["reviews_per_product"] = [
            {"name": name, "total": total}
            for name, total in Counter(
                row["product_name"] for row in reviews if row["product_name"]
            ).most_common(5)
        ]

        context["pizzas_error"] = self.pizzas_error
        context["endpoints"] = ENDPOINTS
        context["recent_calls"] = recent_calls()

        started = time.perf_counter()
        try:
            clients = list_clients()
            context["api_health"] = {
                "ok": True,
                "latency_ms": round((time.perf_counter() - started) * 1000, 1),
                "clients_count": len(clients),
                "error": None,
            }
        except ApiError as exc:
            context["api_health"] = {
                "ok": False,
                "latency_ms": round((time.perf_counter() - started) * 1000, 1),
                "clients_count": 0,
                "error": exc.message,
            }
        return context


class ProductListView(StaffRequiredMixin, ListView):
    """Every mirrored pizza, including the ones already out of the API."""

    model = Product
    template_name = "dashboard/product_list.html"
    context_object_name = "products"
    paginate_by = 20

    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        self.pizzas_error: str | None = None
        try:
            catalog_services.refresh_catalog()
        except ApiError as exc:
            self.pizzas_error = exc.message
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self) -> Any:
        queryset = Product.objects.all()
        search = self.request.GET.get("q", "").strip()[:80]
        if search:
            queryset = queryset.filter(name__icontains=search)
        return queryset

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["search"] = self.request.GET.get("q", "").strip()[:80]
        context["pizzas_error"] = self.pizzas_error
        return context


class ProductCreateView(StaffRequiredMixin, FormView):
    """Create a pizza with ``POST /pizzas/``."""

    form_class = PizzaForm
    template_name = "dashboard/product_form.html"
    success_url = reverse_lazy("dashboard:product_list")

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["pizza"] = None
        return context

    def form_valid(self, form: PizzaForm) -> HttpResponse:
        try:
            product = catalog_services.create_pizza(
                flavor=form.cleaned_data["flavor"],
                description=form.cleaned_data["description"],
                price=form.cleaned_data["price"],
            )
        except ApiError as exc:
            _add_api_errors(form, exc)
            return self.form_invalid(form)
        messages.success(self.request, f"Pizza “{product.name}” criada na API.")
        return super().form_valid(form)


class ProductUpdateView(StaffRequiredMixin, FormView):
    """Change flavor, description and price with ``PATCH /pizzas/<uuid>/``."""

    form_class = PizzaForm
    template_name = "dashboard/product_form.html"
    success_url = reverse_lazy("dashboard:product_list")

    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        self.api_id = str(self.kwargs["api_id"])
        try:
            self.remote_pizza = pizza_api.fetch_pizza(self.api_id)
        except ApiError as exc:
            messages.error(request, f"Não foi possível carregar a pizza: {exc.message}")
            return redirect("dashboard:product_list")
        if self.remote_pizza is None:
            raise Http404("Pizza não encontrada na API.")
        return super().dispatch(request, *args, **kwargs)

    def get_initial(self) -> dict[str, Any]:
        row = self.remote_pizza or {}
        return {
            "flavor": row.get("flavor", ""),
            "description": row.get("description", ""),
            "price": row.get("price", ""),
        }

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["pizza"] = self.remote_pizza
        return context

    def form_valid(self, form: PizzaForm) -> HttpResponse:
        try:
            product = catalog_services.update_pizza(
                api_id=self.api_id,
                flavor=form.cleaned_data["flavor"],
                description=form.cleaned_data["description"],
                price=form.cleaned_data["price"],
            )
        except ApiError as exc:
            _add_api_errors(form, exc)
            return self.form_invalid(form)
        messages.success(self.request, f"Pizza “{product.name}” atualizada na API.")
        return super().form_valid(form)


class ProductDeleteView(StaffRequiredMixin, View):
    """Delete a pizza with ``DELETE /pizzas/<uuid>/`` (409 when it has reviews)."""

    template_name = "dashboard/product_confirm_delete.html"

    def _fetch(self, api_id: str) -> dict[str, Any]:
        row = pizza_api.fetch_pizza(api_id)
        if row is None:
            raise Http404("Pizza não encontrada na API.")
        return row

    def get(self, request: HttpRequest, api_id: Any, *args: Any, **kwargs: Any) -> HttpResponse:
        try:
            row = self._fetch(str(api_id))
        except ApiError as exc:
            messages.error(request, f"Não foi possível carregar a pizza: {exc.message}")
            return redirect("dashboard:product_list")
        return render(request, self.template_name, {"pizza": row})

    def post(self, request: HttpRequest, api_id: Any, *args: Any, **kwargs: Any) -> HttpResponse:
        try:
            row = self._fetch(str(api_id))
            catalog_services.delete_pizza(str(api_id))
        except ApiError as exc:
            messages.error(request, f"Não foi possível excluir: {exc.message}")
            return redirect("dashboard:product_list")
        messages.success(request, f"Pizza “{row.get('flavor')}” excluída da API.")
        return redirect("dashboard:product_list")


class OrderManageListView(StaffRequiredMixin, ListView):
    """Every order, filterable by status and customer."""

    model = Order
    template_name = "dashboard/order_list.html"
    context_object_name = "orders"
    paginate_by = 20

    def get_queryset(self) -> Any:
        queryset = Order.objects.select_related("customer").prefetch_related("items")
        status = self.request.GET.get("status", "").strip()
        if status in Order.Status.values:
            queryset = queryset.filter(status=status)
        search = self.request.GET.get("q", "").strip()[:80]
        if search:
            queryset = queryset.filter(customer_name__icontains=search)
        return queryset.order_by("-created_at")

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["statuses"] = Order.Status.choices
        context["active_status"] = self.request.GET.get("status", "").strip()
        context["search"] = self.request.GET.get("q", "").strip()[:80]
        return context


class OrderStatusUpdateView(StaffRequiredMixin, View):
    """POST only: the owner moves an order through its statuses."""

    http_method_names = ["post"]

    def post(self, request: HttpRequest, pk: int, *args: Any, **kwargs: Any) -> HttpResponse:
        order = get_object_or_404(Order, pk=pk)
        status = request.POST.get("status", "")
        if status not in Order.Status.values:
            messages.error(request, "Status inválido.")
            return redirect("dashboard:order_list")
        order.status = status
        order.save(update_fields=["status", "updated_at"])
        messages.success(request, f"Pedido #{order.pk} agora está “{order.get_status_display()}”.")
        return redirect("dashboard:order_list")


class ClientListView(StaffRequiredMixin, TemplateView):
    """Clients listed straight from the API (GET /clients/)."""

    template_name = "dashboard/client_list.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        search = self.request.GET.get("q", "").strip()[:80]
        context["search"] = search
        context["api_error"] = None
        context["clients"] = []
        try:
            clients = list_clients()
        except ApiError as exc:
            context["api_error"] = exc.message
            return context

        if search:
            term = search.lower()
            clients = [
                client
                for client in clients
                if term in str(client.get("name", "")).lower()
                or term in str(client.get("nickname", "")).lower()
                or term in str(client.get("phone", "")).lower()
            ]
        context["clients"] = sorted(clients, key=lambda item: str(item.get("name", "")).lower())
        return context


class ClientDetailView(StaffRequiredMixin, DetailView):
    """One client fetched live from the API (GET /clients/<uuid>/)."""

    template_name = "dashboard/client_detail.html"

    def get_object(self, queryset: Any = None) -> dict[str, Any]:
        client_id = str(self.kwargs["client_id"])
        try:
            client = fetch_client(client_id)
        except ApiError as exc:
            self.api_error = exc.message
            return {}
        if client is None:
            self.api_error = "Cliente não encontrado na API."
            return {}
        return client

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["client"] = self.object
        context["api_error"] = getattr(self, "api_error", None)
        context["recent_calls"] = recent_calls()
        return context
