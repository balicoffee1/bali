from django.db import models
from colorfield.fields import ColorField

class ColorModel(models.Model):
    title = models.CharField(verbose_name="название", max_length=100, default="")
    color = ColorField(max_length=7, default='#FF0000', verbose_name="Цвет")
    
    class Meta:
        verbose_name = ("Цвет")
        verbose_name_plural = ("Цвета")


class MarkdownModel(models.Model):
    title = models.CharField(verbose_name="Название", max_length=100, default="")
    text = models.TextField(verbose_name="Текст")
    
    class Meta:
        verbose_name = ("Моковая политика")
        verbose_name_plural = ("Моковая политика")