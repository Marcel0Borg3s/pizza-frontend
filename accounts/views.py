"""Account views: registration, login, logout and profile."""

from __future__ import annotations

from typing import Any

from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView, LogoutView
from django.http import HttpResponse
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import FormView, TemplateView

from accounts import services
from accounts.forms import LoginForm, RegisterForm
from core.api import ApiError
from orders.models import Order


class RegisterView(FormView):
    """Create the client in the API and the local login in one step."""

    template_name = "accounts/register.html"
    form_class = RegisterForm

    def dispatch(self, request: Any, *args: Any, **kwargs: Any) -> HttpResponse:
        if request.user.is_authenticated:
            messages.info(request, "Você já está autenticado.")
            return redirect("catalog:home")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form: RegisterForm) -> HttpResponse:
        try:
            user = services.register_customer(form.cleaned_data)
        except ApiError as exc:
            self._apply_api_errors(form, exc)
            return self.form_invalid(form)

        auth_login(self.request, user)
        messages.success(
            self.request,
            "Cadastro concluído. Seu cliente foi criado na API e você já está conectado.",
        )
        return redirect("catalog:home")

    @staticmethod
    def _apply_api_errors(form: RegisterForm, exc: ApiError) -> None:
        """Translate API validation errors into form errors."""
        field_errors = exc.field_errors
        for field, error_messages in field_errors.items():
            target = field if field in form.fields else None
            for error_message in error_messages:
                form.add_error(target, f"API: {error_message}")
        if not field_errors:
            detail = exc.details.get("detail")
            form.add_error(None, str(detail) if detail else exc.message)


class SignInView(LoginView):
    """Local login for accounts created through the registration form."""

    template_name = "accounts/login.html"
    form_class = LoginForm
    redirect_authenticated_user = True

    def get_success_url(self) -> str:
        next_url = self.get_redirect_url()
        return next_url or str(reverse_lazy("catalog:home"))


class SignOutView(LogoutView):
    """POST only, so a link cannot log the user out."""

    next_page = reverse_lazy("catalog:home")


class ProfileView(LoginRequiredMixin, TemplateView):
    """Show the client data fetched live from the API."""

    template_name = "accounts/profile.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        user = self.request.user
        profile = getattr(user, "profile", None)
        context["profile"] = profile
        context["orders_count"] = Order.objects.filter(customer=user).count()
        context["api_error"] = None
        context["remote_client"] = None
        try:
            context["remote_client"] = services.sync_profile_from_api(user)
        except ApiError as exc:
            context["api_error"] = exc.message
        return context
