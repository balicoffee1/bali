from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticatedOrReadOnly

from .models import ColorModel, MarkdownModel
from .serializers import ColorModelSerializer, MarkdownModelSerializer


class ColorModelViewSet(viewsets.ModelViewSet):
    # M0: раньше AllowAny на полном ModelViewSet — любой анонимный запрос
    # мог создавать/менять/удалять записи (не только читать). Чтение
    # (публичная тема оформления) остаётся открытым, запись требует авторизации.
    queryset = ColorModel.objects.all()
    serializer_class = ColorModelSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]


class MarkdownModelViewSet(viewsets.ModelViewSet):
    queryset = MarkdownModel.objects.all()
    serializer_class = MarkdownModelSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
