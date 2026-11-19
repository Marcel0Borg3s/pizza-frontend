"""Root URL configuration."""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("conta/", include("accounts.urls")),
    path("pedidos/", include("orders.urls")),
    path("avaliacoes/", include("reviews.urls")),
    path("painel/", include("dashboard.urls")),
    path("", include("catalog.urls")),
]
