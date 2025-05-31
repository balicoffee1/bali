from django.contrib import admin

from .models import CartItem, ShoppingCart

class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 1
    fields = ("product", "amount", "item_total_price")
    readonly_fields = ("item_total_price",)

    def item_total_price(self, obj):
        return obj.product.price * obj.amount if obj.product and obj.amount else "-"
    item_total_price.short_description = "Полная цена товара"

class ShoppingCartAdmin(admin.ModelAdmin):
    list_display = ("user", "is_active")
    inlines = [CartItemInline]

admin.site.register(ShoppingCart, ShoppingCartAdmin)
admin.site.register(CartItem)  
