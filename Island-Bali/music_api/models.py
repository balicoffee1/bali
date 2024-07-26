from django.db import models


class Music(models.Model):
    title = models.CharField(max_length=250, verbose_name="Название песни")
    author = models.CharField(max_length=255, verbose_name="Имя исполнителя")
    track_id = models.CharField(max_length=100, unique=True,
                                verbose_name="ID трека")
    cover_image_url = models.URLField(verbose_name="URL обложки")
    song = models.FileField(upload_to='', max_length=100,
                            verbose_name="Файл песни",
                            help_text="Загрузите файл песни")

    class Meta:
        verbose_name = "Музыкальный трек"
        verbose_name_plural = "Музыкальные треки"

    def __str__(self) -> str:
        return f"{self.author} - {self.title}"
