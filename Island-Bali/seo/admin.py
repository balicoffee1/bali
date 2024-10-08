from django.contrib import admin
from .models import ColorModel

@admin.register(ColorModel)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['id', 'color']
