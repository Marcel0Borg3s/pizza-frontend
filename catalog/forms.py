"""Owner forms for the catalog.

The form mirrors ``POST/PATCH /pizzas/``: the API only knows ``flavor``,
``description`` and ``price``, so those are the only fields the owner edits.
"""

from __future__ import annotations

from decimal import Decimal

from django import forms
from django.conf import settings

from accounts.forms import INPUT_CLASS

TEXTAREA_CLASS = INPUT_CLASS + " min-h-24"


class PizzaForm(forms.Form):
    """Create and update a pizza in the API from the owner panel."""

    flavor = forms.CharField(
        label="Sabor",
        max_length=50,
        widget=forms.TextInput(attrs={"class": INPUT_CLASS, "maxlength": 50}),
    )
    price = forms.DecimalField(
        label="Preço",
        max_digits=6,
        decimal_places=2,
        min_value=Decimal("0.01"),
        widget=forms.NumberInput(attrs={"class": INPUT_CLASS, "step": "0.01", "min": "0.01"}),
    )
    description = forms.CharField(
        label="Descrição",
        max_length=500,
        widget=forms.Textarea(attrs={"class": TEXTAREA_CLASS, "rows": 3}),
    )

    def clean_flavor(self) -> str:
        flavor = " ".join(self.cleaned_data["flavor"].split())
        if not flavor:
            raise forms.ValidationError("Informe o sabor da pizza.")
        return flavor


class ProductSearchForm(forms.Form):
    """Simple filter used by the owner product list."""

    q = forms.CharField(
        required=False,
        label="Buscar",
        max_length=80,
        widget=forms.TextInput(
            attrs={
                "class": INPUT_CLASS,
                "placeholder": f"Buscar em {settings.SITE_NAME}",
                "aria-label": "Buscar produtos",
            }
        ),
    )
