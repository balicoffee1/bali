from django.contrib import admin

from menu_coffee_product.models import Product, SeasonMenu
from staff.models import Staff

from .models import Acquiring, City, CoffeeShop, CoffeeShopTelegramRecipient, CrmSystem


class TelegramRecipientInline(admin.TabularInline):
    model = CoffeeShopTelegramRecipient
    extra = 0
    fields = ('telegram_id', 'telegram_username', 'first_name', 'is_active', 'created_at')
    readonly_fields = ('created_at',)


class AcquiringInline(admin.TabularInline):
    model = Acquiring
    extra = 0
    fields = ('name', 'login', 'password') 

class ProductInline(admin.TabularInline):
    model = Product
    extra = 0
    

class SeasonMenuInline(admin.TabularInline):
    model = SeasonMenu
    extra = 0


class CoffeeShopAdmin(admin.ModelAdmin):
    list_display = (
        "__str__", "city", "street", "building_number", "has_lifepay", "email", "crm_system",
        "acquiring", "time_open", "time_close",
    )
    list_filter = ("city",)
    search_fields = ("city__name", "street", "building_number")
    inlines = [TelegramRecipientInline, ProductInline, SeasonMenuInline]
    fieldsets = (
        ("Основная информация", {"fields": (
            "city", "street", "building_number", "phone_number", "email",
            "telegram_id", "telegram_username",
        )}),
        ("Эквайринг LifePay (СБП)", {
            "fields": ("lifepay_login", "lifepay_api_key"),
            "description": "Логин (телефон) и API ключ из кабинета LifePay (home.life-pay.ru).",
        }),
        ("CRM интеграция", {
            "fields": ("crm_system", "crm_layer_name", "crm_email", "crm_password", "inn"),
            "classes": ("collapse",),
        }),
        ("Дополнительная информация", {
            "fields": ("acquiring", "time_open", "time_close"),
            "classes": ("collapse",),
        }),
    )

    @admin.display(description="LifePay / СБП", boolean=True)
    def has_lifepay(self, obj):
        return bool(obj.lifepay_api_key and obj.lifepay_login)

    def get_queryset(self, request):
        user_role = request.user.role

        if request.user.is_superuser or user_role == "owner":
            return CoffeeShop.objects.all()

        elif user_role == "admin":
            place_of_work = Staff.objects.filter(
                users=request.user).first().place_of_work.building_number
            return CoffeeShop.objects.filter(building_number=place_of_work)

        else:
            return CoffeeShop.objects.none()

    def save_model(self, request, obj, form, change) -> None:
        user_creating_staff = request.user
        if not change:
            if user_creating_staff.is_superuser or user_creating_staff.role == 'owner':
                obj.save()
            elif user_creating_staff.role == 'admin':
                raise Exception('Вы не можете создавать точки')

        super().save_model(request, obj, form, change)


class CityAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)


admin.site.register(City, CityAdmin)
admin.site.register(CoffeeShop, CoffeeShopAdmin)
admin.site.register(CrmSystem)
admin.site.register(Acquiring)
