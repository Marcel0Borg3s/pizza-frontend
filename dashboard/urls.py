"""Owner panel URLs."""

from django.urls import path

from dashboard.views import (
    ClientDetailView,
    ClientListView,
    DashboardIndexView,
    OrderManageListView,
    OrderStatusUpdateView,
    ProductCreateView,
    ProductDeleteView,
    ProductListView,
    ProductUpdateView,
)

app_name = "dashboard"

urlpatterns = [
    path("", DashboardIndexView.as_view(), name="index"),
    path("produtos/", ProductListView.as_view(), name="product_list"),
    path("produtos/novo/", ProductCreateView.as_view(), name="product_create"),
    path("produtos/<uuid:api_id>/editar/", ProductUpdateView.as_view(), name="product_update"),
    path("produtos/<uuid:api_id>/excluir/", ProductDeleteView.as_view(), name="product_delete"),
    path("pedidos/", OrderManageListView.as_view(), name="order_list"),
    path("pedidos/<int:pk>/status/", OrderStatusUpdateView.as_view(), name="order_status"),
    path("clientes/", ClientListView.as_view(), name="client_list"),
    path("clientes/<uuid:client_id>/", ClientDetailView.as_view(), name="client_detail"),
]
