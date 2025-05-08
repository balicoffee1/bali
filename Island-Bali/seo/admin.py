from django.contrib import admin
from .models import ColorModel, MarkdownModel

@admin.register(ColorModel)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['id', 'color']

@admin.register(MarkdownModel)
class MarkdownAdmin(admin.ModelAdmin):
    list_display = ['id', 'title']
    list_filter = ['title']
    search_fields = ['title']
    ordering = ['-id']