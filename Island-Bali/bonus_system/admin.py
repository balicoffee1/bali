from django.contrib import admin

from bonus_system.models import DiscountCard


class CustomModelAdmin(admin.ModelAdmin):
    def __init__(self, model, admin_site, *args, **kwargs):
        self.list_display = [field.name for field in model._meta.fields]
        super(CustomModelAdmin, self).__init__(model, admin_site)


@admin.register(DiscountCard)
class DiscountCardAdmin(CustomModelAdmin):
    """
    Админка для модели DiscountCard.
    """

    list_display = ("user", "is_active", "qr_code", "discount_rate",
                    "total_spent")
    search_fields = ("user__login", "user__first_name", "user__last_name")
    list_filter = ("is_active",)
    readonly_fields = ("qr_code_image",)

    def save_model(self, request, obj, form, change):
        """
        При сохранении модели в админке активирует скидочную карту, если нужно.
        """
        # obj.activate_card()
        super().save_model(request, obj, form, change)

# admin.site.register(DiscountCard, DiscountCardAdmin)
