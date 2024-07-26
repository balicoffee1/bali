from django.contrib import admin

from music_api.models import Music


# Register your models here.
class CustomModelAdmin(admin.ModelAdmin):
    def __init__(self, model, admin_site, *args, **kwargs):
        self.list_display = [field.name for field in model._meta.fields]
        super(CustomModelAdmin, self).__init__(model, admin_site)


@admin.register(Music)
class MusicAdmin(CustomModelAdmin):
    pass
