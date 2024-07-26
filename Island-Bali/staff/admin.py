from django.contrib import admin

from staff.models import Shift, Staff


@admin.register(Staff)
class StaffAdmin(admin.ModelAdmin):
    list_display = (
        "users",
        "place_of_work",
    )
    list_filter = ()
    search_fields = ("users__first_name", "users__last_name", "users__email")

    def get_queryset(self, request):
        user_role = request.user.role

        if user_role == "admin":
            staff_instance = Staff.objects.filter(users=request.user).first()
            return Staff.objects.filter(
                place_of_work=staff_instance.place_of_work)

        elif user_role == "owner":
            return Staff.objects.all()

        return Staff.objects.none()


@admin.register(Shift)
class ShiftAdmin(admin.ModelAdmin):
    list_display = (
        "staff",
        "start_time",
        "end_time",
        "number_orders_closed",
        "amount_closed_orders",
        "status_shift",
    )
    list_filter = ("status_shift",)
    search_fields = ("staff__users__first_name", "staff__users__last_name")
