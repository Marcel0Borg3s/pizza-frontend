"""Review views: public list and authenticated creation."""

from __future__ import annotations

from typing import Any

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import FormView, ListView

from core.api import ApiError
from orders.models import OrderItem
from reviews import services
from reviews.forms import ReviewForm


class ReviewListView(ListView):
    """Public list: everyone can read the reviews, straight from ``GET /reviews/``."""

    template_name = "reviews/list.html"
    context_object_name = "reviews"
    paginate_by = 12

    def get_queryset(self) -> list[dict[str, Any]]:
        try:
            self.rows = services.visible_reviews()
            self.api_error: str | None = None
        except ApiError as exc:
            self.rows = []
            self.api_error = exc.message
        return self.rows

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["summary"] = services.rating_summary(self.rows)
        context["api_error"] = self.api_error
        return context


class ReviewCreateView(LoginRequiredMixin, FormView):
    """Write a review for one item of the customer's own order."""

    form_class = ReviewForm
    template_name = "reviews/form.html"

    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        if request.user.is_authenticated:
            self.order_item = get_object_or_404(
                OrderItem.objects.select_related("product", "order"),
                pk=kwargs["item_id"],
                order__customer=request.user,
            )
            if self.order_item.has_review:
                messages.info(request, "Este item já foi avaliado. Obrigado!")
                return redirect("catalog:detail", slug=self.order_item.product.slug)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["order_item"] = getattr(self, "order_item", None)
        return context

    def form_valid(self, form: ReviewForm) -> HttpResponse:
        try:
            review = services.create_review(
                order_item=self.order_item,
                author=self.request.user,
                rating=form.cleaned_data["rating"],
                comment=form.cleaned_data["comment"],
            )
        except ApiError as exc:
            form.add_error(None, exc.message)
            return self.form_invalid(form)
        messages.success(self.request, "Avaliação publicada. Obrigado pelo retorno!")
        return redirect("catalog:detail", slug=review.product.slug)
