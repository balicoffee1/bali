from django.contrib import admin

from staff.models import Staff

from .models import Orders


class OrdersAdmin(admin.ModelAdmin):
    list_display = (
        "__str__",
        "user",
        "city_choose",
        "status_orders",
        "coffee_shop",
        "time_is_finish",
    )
    list_filter = ("city_choose", "coffee_shop", "time_is_finish")
    search_fields = ("user__username", "coffee_shop__street")

    def get_queryset(self, request):
        user_role = request.user.role

        if user_role == "admin":
            place_of_work = (
                Staff.objects.filter(users=request.user).first().place_of_work)
            return Orders.objects.filter(coffee_shop=place_of_work)

        elif user_role == "owner":
            return Orders.objects.all()

        else:
            return Orders.objects.none()

    def save_model(self, request, obj, form, change) -> None:
        user_creating_order = request.user
        if not change:
            if user_creating_order.role == 'owner':
                obj.save()

            elif user_creating_order.role == 'admin':
                place_of_work = Staff.objects.filter(
                    users=request.user).first().place_of_work

                if place_of_work == obj.coffee_shop:
                    obj.save()

                else:
                    raise Exception('Вы можете '
                                    'создавать заказы только на своей точке')

        super().save_model(request, obj, form, change)


admin.site.register(Orders, OrdersAdmin)
