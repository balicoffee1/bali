from django.contrib import admin

from .models import CartItem, ShoppingCart

class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 1
    fields = ("product", "amount", "item_total_price")
    readonly_fields = ("item_total_price",)

    def item_total_price(self, obj):
        return obj.product.price * obj.amount
    item_total_price.short_description = "Полная цена товара"

class CartItemAdmin(admin.ModelAdmin):
    list_display = ("product", "amount")
    list_filter = ("product",)
    search_fields = ("product__name",)
    inlines = [CartItemInline]


admin.site.register(CartItem, CartItemAdmin)
admin.site.register(ShoppingCart)
