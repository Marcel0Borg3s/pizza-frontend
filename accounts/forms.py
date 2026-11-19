"""Account forms with validation that mirrors the API contract."""

from __future__ import annotations

import re
from typing import Any

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UsernameField
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.core.exceptions import ValidationError
from django.core.validators import MinLengthValidator

INPUT_CLASS = (
    "block w-full rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm "
    "text-stone-900 shadow-sm transition placeholder:text-stone-400 "
    "focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/40 "
    "dark:border-stone-600 dark:bg-stone-800 dark:text-stone-100 "
    "dark:placeholder:text-stone-500 dark:focus:border-brand-400"
)

PASSWORD_INPUT_CLASS = INPUT_CLASS + " pr-11"


class RegisterForm(forms.Form):
    """Customer sign up. The nickname is unique inside the API."""

    name = forms.CharField(
        label="Nome completo",
        max_length=200,
        widget=forms.TextInput(attrs={"class": INPUT_CLASS, "autocomplete": "name"}),
    )
    nickname = forms.CharField(
        label="Apelido",
        max_length=30,
        help_text="Único. É o que você usa para entrar no site.",
        widget=forms.TextInput(
            attrs={"class": INPUT_CLASS, "autocomplete": "username", "autocapitalize": "none"}
        ),
    )
    phone = forms.CharField(
        label="Telefone / WhatsApp",
        max_length=20,
        widget=forms.TextInput(
            attrs={
                "class": INPUT_CLASS,
                "inputmode": "tel",
                "autocomplete": "tel-national",
                "placeholder": "(19) 99999-9999",
            }
        ),
    )
    address = forms.CharField(
        label="Endereço",
        max_length=100,
        widget=forms.TextInput(attrs={"class": INPUT_CLASS, "autocomplete": "address-line1"}),
    )
    number = forms.CharField(
        label="Número",
        max_length=10,
        widget=forms.TextInput(attrs={"class": INPUT_CLASS, "autocomplete": "address-line2"}),
    )
    neighborhood = forms.CharField(
        label="Bairro",
        max_length=100,
        widget=forms.TextInput(attrs={"class": INPUT_CLASS}),
    )
    city = forms.CharField(
        label="Cidade",
        max_length=100,
        widget=forms.TextInput(attrs={"class": INPUT_CLASS, "autocomplete": "address-level2"}),
    )
    password = forms.CharField(
        label="Senha",
        validators=[MinLengthValidator(8)],
        widget=forms.PasswordInput(
            attrs={"class": PASSWORD_INPUT_CLASS, "autocomplete": "new-password"}
        ),
        help_text="Mínimo de 8 caracteres, evitando senhas comuns.",
    )
    password_confirm = forms.CharField(
        label="Confirme a senha",
        widget=forms.PasswordInput(
            attrs={"class": PASSWORD_INPUT_CLASS, "autocomplete": "new-password"}
        ),
    )

    def clean_nickname(self) -> str:
        nickname = str(self.cleaned_data["nickname"]).strip().lower()
        validator = UnicodeUsernameValidator()
        try:
            validator(nickname)
        except ValidationError as exc:
            raise forms.ValidationError(
                "Use apenas letras, números e os caracteres @ . + - _."
            ) from exc
        if get_user_model().objects.filter(username__iexact=nickname).exists():
            raise forms.ValidationError("Este apelido já tem conta aqui. Tente entrar.")
        return nickname

    def clean_phone(self) -> str:
        digits = re.sub(r"\D", "", str(self.cleaned_data["phone"]))
        if len(digits) not in (10, 11):
            raise forms.ValidationError("Informe DDD + número, com 10 ou 11 dígitos.")
        return digits

    def clean(self) -> dict[str, Any]:
        cleaned = super().clean()
        password = cleaned.get("password")
        confirm = cleaned.get("password_confirm")
        if password and confirm and password != confirm:
            self.add_error("password_confirm", "As senhas não coincidem.")
        if password:
            candidate = get_user_model()(username=cleaned.get("nickname", ""))
            try:
                validate_password(password, user=candidate)
            except ValidationError as exc:
                self.add_error("password", exc)
        return cleaned


class LoginForm(AuthenticationForm):
    """Authentication form with the project styling."""

    username = UsernameField(
        label="Apelido",
        widget=forms.TextInput(
            attrs={"class": INPUT_CLASS, "autocomplete": "username", "autofocus": True}
        ),
    )
    password = forms.CharField(
        label="Senha",
        widget=forms.PasswordInput(
            attrs={"class": PASSWORD_INPUT_CLASS, "autocomplete": "current-password"}
        ),
    )
