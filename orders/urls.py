"""Order URLs."""

from django.urls import path

from orders.views import (
    AddToCartView,
    CartDetailView,
    CheckoutView,
    OrderCancelView,
    OrderDetailView,
    OrderListView,
    RemoveFromCartView,
    UpdateCartView,
)

app_name = "orders"

urlpatterns = [
    path("carrinho/", CartDetailView.as_view(), name="cart"),
    path("carrinho/adicionar/<int:product_id>/", AddToCartView.as_view(), name="cart_add"),
    path("carrinho/atualizar/<int:product_id>/", UpdateCartView.as_view(), name="cart_update"),
    path("carrinho/remover/<int:product_id>/", RemoveFromCartView.as_view(), name="cart_remove"),
    path("finalizar/", CheckoutView.as_view(), name="checkout"),
    path("", OrderListView.as_view(), name="list"),
    path("<int:pk>/", OrderDetailView.as_view(), name="detail"),
    path("<int:pk>/cancelar/", OrderCancelView.as_view(), name="cancel"),
]
