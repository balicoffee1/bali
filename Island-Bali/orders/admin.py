from django.contrib import admin

from staff.models import Staff

from .models import Orders
from .services import OrderStateService


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

        if request.user.is_superuser or user_role == "owner":
            return Orders.objects.all()

        elif user_role == "admin":
            place_of_work = (
                Staff.objects.filter(users=request.user).first().place_of_work)
            return Orders.objects.filter(coffee_shop=place_of_work)

        else:
            return Orders.objects.none()

    # Доменные поля заказа: менять их обычным obj.save() из админки нельзя.
    DOMAIN_FIELDS = ('status_orders', 'payment_status')

    def save_model(self, request, obj, form, change) -> None:
        """
        M7: изменение статуса из админки Django идёт через OrderStateService.

        Раньше здесь был обычный obj.save() — то есть админка была ещё одной
        точкой мутации состояния заказа в обход сервиса. Пока приложение
        перечитывало заказы каждые 5 секунд, это было незаметно: клиент всё
        равно рано или поздно видел новый статус. После перехода на WebSocket
        такой записи никто не публикует, и приложение о ней не узнаёт вообще —
        статус в БД меняется, а у пользователя висит старый экран.

        admin_override как раз для этого и сделан: он не проверяет допустимость
        перехода (админка — инструмент ручного исправления, и блокировать её
        state machine нельзя), но инкрементирует version/event_seq, публикует
        событие и пишет запись в audit trail.
        """
        user_creating_order = request.user
        if not change:
            if user_creating_order.is_superuser or user_creating_order.role == 'owner':
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
            OrderStateService.order_created(obj.id)
            return

        changed_domain_fields = [
            field for field in self.DOMAIN_FIELDS
            if field in getattr(form, 'changed_data', [])
        ]
        if not changed_domain_fields:
            super().save_model(request, obj, form, change)
            return

        # Остальные поля формы сохраняем обычным путём, доменным временно
        # возвращаем прежние значения — иначе они уехали бы в БД мимо сервиса,
        # и он не увидел бы никакого перехода.
        new_values = {field: getattr(obj, field) for field in changed_domain_fields}
        for field in changed_domain_fields:
            setattr(obj, field, form.initial.get(field, getattr(obj, field)))
        super().save_model(request, obj, form, change)

        OrderStateService.admin_override(
            obj.id,
            admin_user=request.user,
            new_order_status=new_values.get('status_orders'),
            new_payment_status=new_values.get('payment_status'),
            reason=f'Изменение статуса через админку Django ({request.user})',
            request=request,
        )
        obj.refresh_from_db()


admin.site.register(Orders, OrdersAdmin)
