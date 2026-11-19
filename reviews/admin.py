"""Reviews admin."""

from django.contrib import admin

from reviews.models import Review


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("product", "rating", "author", "created_at")
    list_filter = ("rating", "created_at")
    search_fields = ("product__name", "comment", "author__username")
    readonly_fields = ("order_item", "product", "author", "created_at")
