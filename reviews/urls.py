"""Review URLs."""

from django.urls import path

from reviews.views import ReviewCreateView, ReviewListView

app_name = "reviews"

urlpatterns = [
    path("", ReviewListView.as_view(), name="list"),
    path("pedido/<int:item_id>/", ReviewCreateView.as_view(), name="create"),
]
