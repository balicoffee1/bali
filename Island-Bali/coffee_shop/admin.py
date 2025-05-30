from django.contrib import admin

from menu_coffee_product.models import Product, SeasonMenu
from staff.models import Staff

from .models import Acquiring, City, CoffeeShop, CrmSystem


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
        "__str__", "city", "street", "building_number", "email", "crm_system",
        "acquiring", "time_open", "time_close",)
    list_filter = ("city",)
    search_fields = ("city__name", "street", "building_number")
    inlines = [ProductInline, SeasonMenuInline]
    fieldsets = (
        (None, {"fields": (
            "city", "street", "telegram_id", "building_number", "email",
            "telegram_username", "crm_layer_name", "crm_password", 
            "lifepay_api_key", "lifepay_login",)}),
        ("Дополнительная информация",
         {"fields": ("crm_system", "acquiring", "time_open", "time_close"),
          "classes": ("collapse",),
          "description": "Это дополнительная информация для кофейни."}),
    )

    def get_queryset(self, request):
        user_role = request.user.role

        if user_role == "admin":
            place_of_work = Staff.objects.filter(
                users=request.user).first().place_of_work.building_number
            return CoffeeShop.objects.filter(building_number=place_of_work)

        elif user_role == "owner":
            return CoffeeShop.objects.all()

        else:
            return CoffeeShop.objects.none()

    def save_model(self, request, obj, form, change) -> None:
        user_creating_staff = request.user
        if not change:
            if user_creating_staff.role == 'owner':
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
