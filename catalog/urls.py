"""Catalog URLs."""

from django.urls import path

from catalog.views import ProductDetailView, ProductListView

app_name = "catalog"

urlpatterns = [
    path("", ProductListView.as_view(), name="home"),
    path("produto/<slug:slug>/", ProductDetailView.as_view(), name="detail"),
]
