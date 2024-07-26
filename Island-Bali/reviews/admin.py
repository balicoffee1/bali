from django.contrib import admin

from .models import ReviewsCoffeeShop


class ReviewsCoffeeShopAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'coffee_shop', 'evaluation', 'very_tasty', 'wide_range',
        'nice_prices', 'comments')
    list_filter = (
        'coffee_shop', 'evaluation', 'very_tasty', 'wide_range', 'nice_prices')
    search_fields = ('user__username', 'user__email', 'comments')
    readonly_fields = (
        'user', 'coffee_shop', 'orders', 'evaluation', 'very_tasty',
        'wide_range', 'nice_prices', 'comments')

    fieldsets = (
        ('Основная информация', {
            'fields': ('user', 'coffee_shop', 'orders', 'evaluation')
        }),
        ('Оценка качества', {
            'fields': ('very_tasty', 'wide_range', 'nice_prices')
        }),
        ('Комментарии', {
            'fields': ('comments',)
        }),
    )

    def has_add_permission(self, request, obj=None):
        return False


admin.site.register(ReviewsCoffeeShop, ReviewsCoffeeShopAdmin)
