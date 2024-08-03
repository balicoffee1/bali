from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _

from .models import CustomUser, UserCard


@admin.register(CustomUser)
class UsersAdmin(BaseUserAdmin):
    list_display = ("login", "email", "role", "is_active")
    search_fields = ("login", "email", "role")
    list_filter = ("role", "is_active")
    ordering = ("login",)
    list_per_page = 50
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            "fields": (
                "login", "email", "first_name", "last_name", "phone_number",
                "role", "is_active", 'password1', 'password2', "is_superuser",
                "is_staff")

        }),)
    fieldsets = (
        (None, {"fields": ("login", "password")}),
        (_("Personal info"),
         {"fields": ("first_name", "last_name", "email", "role")}),
        (
            _("Permissions"),
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                ),
            },
        ),
        (_("Important dates"), {"fields": ("last_login",)}),
    )

    def get_queryset(self, request):
        user = request.user.is_superuser
        if user:
            return CustomUser.objects.all()
        else:
            return CustomUser.objects.none()


admin.site.register(UserCard)