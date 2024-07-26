from django.contrib import admin

from .models import CartItem, ShoppingCart


class CartItemAdmin(admin.ModelAdmin):
    list_display = ("product", "amount")
    list_filter = ("product",)
    search_fields = ("product__name",)


admin.site.register(CartItem, CartItemAdmin)
admin.site.register(ShoppingCart)
