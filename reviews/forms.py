"""Review form."""

from __future__ import annotations

from django import forms

from accounts.forms import INPUT_CLASS

RATING_CHOICES = [
    (5, "5 — Excelente"),
    (4, "4 — Muito boa"),
    (3, "3 — Boa"),
    (2, "2 — Deixa a desejar"),
    (1, "1 — Ruim"),
]


class ReviewForm(forms.Form):
    """Rating and comment for a purchased item."""

    rating = forms.TypedChoiceField(
        label="Nota",
        choices=RATING_CHOICES,
        coerce=int,
        widget=forms.RadioSelect(
            attrs={"class": "peer sr-only"},
        ),
    )
    comment = forms.CharField(
        label="Comentário",
        max_length=500,
        min_length=5,
        widget=forms.Textarea(
            attrs={
                "class": INPUT_CLASS + " min-h-28",
                "rows": 4,
                "placeholder": "Como estava a massa, o recheio, a entrega?",
            }
        ),
    )
