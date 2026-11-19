"""Orders admin."""

from django.contrib import admin

from orders.models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("product_name", "unit_price", "quantity")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "customer_name", "status", "total", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("customer_name", "phone", "customer__username")
    readonly_fields = ("total", "created_at", "updated_at")
    inlines = [OrderItemInline]
