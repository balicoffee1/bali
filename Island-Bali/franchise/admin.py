from django.contrib import admin

from .models import FranchiseInfo, FranchiseRequest


class FranchiseRequestAdmin(admin.ModelAdmin):
    readonly_fields = ["name", "number_phone", "text"]
    list_display = ["name", "number_phone"]
    search_fields = ["name", "number_phone"]
    list_filter = ["name"]


class FranchiseInfoAdmin(admin.ModelAdmin):
    list_display = ["id", "text"]
    search_fields = ["text"]


admin.site.register(FranchiseRequest, FranchiseRequestAdmin)
admin.site.register(FranchiseInfo, FranchiseInfoAdmin)
