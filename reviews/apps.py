"""Reviews app: public product reviews written by customers."""

from django.apps import AppConfig


class ReviewsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "reviews"
    verbose_name = "Avaliações"
