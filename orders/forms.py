"""Checkout form with delivery data."""

from __future__ import annotations

import re

from django import forms

from accounts.forms import INPUT_CLASS

TEXTAREA_CLASS = INPUT_CLASS + " min-h-20"


class CheckoutForm(forms.Form):
    """Delivery details, prefilled with the client data from the API."""

    customer_name = forms.CharField(
        label="Nome para entrega",
        max_length=200,
        widget=forms.TextInput(attrs={"class": INPUT_CLASS, "autocomplete": "name"}),
    )
    phone = forms.CharField(
        label="Telefone / WhatsApp",
        max_length=20,
        widget=forms.TextInput(
            attrs={"class": INPUT_CLASS, "inputmode": "tel", "autocomplete": "tel-national"}
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
    notes = forms.CharField(
        label="Observações (opcional)",
        max_length=300,
        required=False,
        widget=forms.Textarea(
            attrs={"class": TEXTAREA_CLASS, "rows": 2, "placeholder": "Sem cebola, campainha..."}
        ),
    )

    def clean_phone(self) -> str:
        digits = re.sub(r"\D", "", str(self.cleaned_data["phone"]))
        if len(digits) not in (10, 11):
            raise forms.ValidationError("Informe DDD + número, com 10 ou 11 dígitos.")
        return digits

    @classmethod
    def initial_from_client(cls, client: dict | None) -> dict[str, str]:
        """Map the API client payload into form initial values."""
        if not client:
            return {}
        return {
            "customer_name": str(client.get("name", "")),
            "phone": str(client.get("phone", "")),
            "address": str(client.get("address", "")),
            "number": str(client.get("number", "")),
            "neighborhood": str(client.get("neighborhood", "")),
            "city": str(client.get("city", "")),
        }
