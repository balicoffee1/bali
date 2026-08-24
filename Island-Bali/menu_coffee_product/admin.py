from django.contrib import admin

from staff.models import Staff

from .models import Addon, Category, Product, SeasonMenu, AdditiveFlavors


class CustomModelAdmin(admin.ModelAdmin):
    def __init__(self, model, admin_site, *args, **kwargs):
        self.list_display = [field.name for field in model._meta.fields]
        super(CustomModelAdmin, self).__init__(model, admin_site)


class AddonInline(admin.TabularInline):
    model = Product.addons.through
    extra = 1
    verbose_name = "Добавка"
    verbose_name_plural = "Добавки"
        


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    inlines = [AddonInline]
    list_display = (
        "id",
        "product",
        "coffee_shop",
        "category",
        "which_menu",
    )
    list_filter = ("coffee_shop", "category")
    search_fields = ("id", "product", "coffee_shop__city__name", "category__name")
    exclude = ("addons", "price")  

    def get_queryset(self, request):
        user_role = request.user.role
        if request.user.is_superuser or user_role == "owner":
            return Product.objects.all()
        elif user_role == "admin":
            place_of_work = Staff.objects.filter(
                users=request.user).first().place_of_work
            return Product.objects.filter(coffee_shop=place_of_work)
        else:
            return Product.objects.none()

    def save_model(self, request, obj, form, change) -> None:
        user_creating_menu = request.user
        if not change:
            if user_creating_menu.is_superuser or user_creating_menu.role == 'owner':
                obj.save()
            elif user_creating_menu.role == 'admin':
                place_of_work = Staff.objects.filter(
                    users=request.user).first().place_of_work

                if place_of_work == obj.coffee_shop:
                    obj.save()

                else:
                    raise Exception(
                        'Вы можете создавать меню только на своей точке')

        super().save_model(request, obj, form, change)


@admin.register(Category)
class CategoryAdmin(CustomModelAdmin):
    list_display = ("name", "coffee_shop", "which_menu")
    list_filter = ("coffee_shop",)
    search_fields = ("name", "coffee_shop__city__name")

    def get_queryset(self, request):
        user_role = request.user.role

        if request.user.is_superuser or user_role == "owner":
            return Category.objects.all()

        elif user_role == "admin":
            place_of_work = Staff.objects.filter(
                users=request.user).first().place_of_work
            return Category.objects.filter(coffee_shop=place_of_work)

        else:
            return Category.objects.none()

    def save_model(self, request, obj, form, change) -> None:
        user_creating_category = request.user
        if not change:
            if user_creating_category.is_superuser or user_creating_category.role == 'owner':
                obj.save()
            elif user_creating_category.role == 'admin':
                place_of_work = Staff.objects.filter(
                    users=request.user).first().place_of_work

                if place_of_work == obj.coffee_shop:
                    obj.save()

                else:
                    raise Exception(
                        'Вы можете создавать категорию только на своей точке')

        super().save_model(request, obj, form, change)


@admin.register(Addon)
class AddonAdmin(CustomModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)


@admin.register(AdditiveFlavors)
class AdditiveFlavorsAdmin(CustomModelAdmin):
    search_fields = ("name",)



admin.site.register(SeasonMenu)


# users/admin.py или любой другой admin.py
from django.contrib import admin
from django_celery_beat.models import PeriodicTask, CrontabSchedule, IntervalSchedule, SolarSchedule, ClockedSchedule

# Отключаем их от админки
admin.site.unregister(PeriodicTask)
admin.site.unregister(CrontabSchedule)
admin.site.unregister(IntervalSchedule)
admin.site.unregister(SolarSchedule)
admin.site.unregister(ClockedSchedule)
