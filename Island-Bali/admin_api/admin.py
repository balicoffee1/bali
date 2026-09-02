from django.contrib import admin
from .models import AdminActivityLog


@admin.register(AdminActivityLog)
class AdminActivityLogAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'user', 'action', 'entity_name', 'entity_id', 'summary', 'ip_address')
    list_filter = ('action', 'entity_name', 'created_at')
    search_fields = ('summary', 'entity_id', 'user__login', 'ip_address')
    readonly_fields = ('created_at', 'user', 'action', 'entity_name', 'entity_id', 'summary', 'changes', 'ip_address')

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
