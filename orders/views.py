"""Cart, checkout and order history views."""

from __future__ import annotations

from typing import Any

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View
from django.views.generic import DetailView, FormView, ListView, TemplateView

from accounts.services import fetch_client
from catalog.models import Product
from core.api import ApiError
from orders.forms import CheckoutForm
from orders.models import Order
from orders.services import Cart, CartError, create_order


def _safe_next(request: HttpRequest, fallback: str) -> str:
    """Return a local ``next`` URL or the fallback (blocks open redirects)."""
    candidate = request.POST.get("next") or request.GET.get("next") or ""
    if candidate and url_has_allowed_host_and_scheme(
        candidate, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return candidate
    return fallback


def _cart(request: HttpRequest) -> Cart:
    return Cart(request.session)


class CartDetailView(TemplateView):
    """Show the cart with quantities and totals."""

    template_name = "orders/cart.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        cart = _cart(self.request)
        context["lines"] = cart.lines()
        context["total"] = cart.total
        return context


class AddToCartView(View):
    """POST only: adds a product to the session cart."""

    http_method_names = ["post"]

    def post(
        self, request: HttpRequest, product_id: int, *args: Any, **kwargs: Any
    ) -> HttpResponse:
        product = get_object_or_404(Product, pk=product_id, is_available=True)
        try:
            quantity = int(request.POST.get("quantity", 1))
        except (TypeError, ValueError):
            quantity = 1
        _cart(request).add(product.pk, quantity)
        messages.success(request, f"{product.name} adicionado ao carrinho.")
        return redirect(_safe_next(request, reverse("catalog:home")))


class UpdateCartView(View):
    """POST only: sets the quantity of one line (0 removes it)."""

    http_method_names = ["post"]

    def post(
        self, request: HttpRequest, product_id: int, *args: Any, **kwargs: Any
    ) -> HttpResponse:
        cart = _cart(request)
        try:
            quantity = int(request.POST.get("quantity", 0))
        except (TypeError, ValueError):
            quantity = 0
        if quantity <= 0:
            cart.remove(product_id)
        else:
            cart.set_quantity(product_id, quantity)
        return redirect("orders:cart")


class RemoveFromCartView(View):
    """POST only: removes a product from the cart."""

    http_method_names = ["post"]

    def post(
        self, request: HttpRequest, product_id: int, *args: Any, **kwargs: Any
    ) -> HttpResponse:
        Cart(request.session).remove(product_id)
        messages.info(request, "Item removido do carrinho.")
        return redirect("orders:cart")


class CheckoutView(LoginRequiredMixin, FormView):
    """Checkout requires a logged customer; delivery data comes from the API."""

    template_name = "orders/checkout.html"
    form_class = CheckoutForm

    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        if request.user.is_authenticated and not _cart(request):
            messages.info(request, "Seu carrinho está vazio. Escolha uma pizza primeiro.")
            return redirect("catalog:home")
        return super().dispatch(request, *args, **kwargs)

    def get_initial(self) -> dict[str, str]:
        initial = super().get_initial()
        profile = getattr(self.request.user, "profile", None)
        if profile is None or not profile.client_id:
            return initial
        try:
            remote_client = fetch_client(str(profile.client_id))
        except ApiError as exc:
            messages.warning(
                self.request,
                f"Não foi possível carregar seus dados da API ({exc.message}). "
                "Preencha os campos manualmente.",
            )
            return initial
        if remote_client is None:
            messages.warning(
                self.request,
                "Seu cadastro não foi encontrado na API. Confira os dados antes de confirmar.",
            )
        return {**initial, **CheckoutForm.initial_from_client(remote_client)}

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        cart = _cart(self.request)
        context["lines"] = cart.lines()
        context["total"] = cart.total
        return context

    def form_valid(self, form: CheckoutForm) -> HttpResponse:
        cart = _cart(self.request)
        delivery = {
            "customer_name": form.cleaned_data["customer_name"],
            "phone": form.cleaned_data["phone"],
            "address": form.cleaned_data["address"],
            "number": form.cleaned_data["number"],
            "neighborhood": form.cleaned_data["neighborhood"],
            "city": form.cleaned_data["city"],
        }
        try:
            order = create_order(
                user=self.request.user,
                cart=cart,
                delivery=delivery,
                notes=form.cleaned_data.get("notes", ""),
            )
        except CartError as exc:
            form.add_error(None, str(exc))
            return self.form_invalid(form)

        messages.success(self.request, f"Pedido #{order.pk} registrado com sucesso.")
        return redirect("orders:detail", pk=order.pk)


class OrderListView(LoginRequiredMixin, ListView):
    """Only the logged customer's own orders."""

    model = Order
    template_name = "orders/order_list.html"
    context_object_name = "orders"
    paginate_by = 10

    def get_queryset(self) -> Any:
        return (
            Order.objects.filter(customer=self.request.user)
            .prefetch_related("items")
            .order_by("-created_at")
        )


class OrderDetailView(LoginRequiredMixin, DetailView):
    """Order details, restricted to its owner (no IDOR)."""

    model = Order
    template_name = "orders/order_detail.html"
    context_object_name = "order"

    def get_queryset(self) -> Any:
        return Order.objects.filter(customer=self.request.user).prefetch_related(
            "items__product", "items__review"
        )


class OrderCancelView(LoginRequiredMixin, View):
    """POST only, and only while the order is still pending."""

    http_method_names = ["post"]

    def post(self, request: HttpRequest, pk: int, *args: Any, **kwargs: Any) -> HttpResponse:
        order = get_object_or_404(Order, pk=pk, customer=request.user)
        if not order.can_cancel:
            messages.error(request, "Este pedido já não pode ser cancelado.")
            return redirect("orders:detail", pk=order.pk)
        order.status = Order.Status.CANCELLED
        order.save(update_fields=["status", "updated_at"])
        messages.success(request, f"Pedido #{order.pk} cancelado.")
        return redirect("orders:detail", pk=order.pk)
