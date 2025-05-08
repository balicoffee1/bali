from rest_framework import viewsets
from rest_framework.permissions import AllowAny

from .models import ColorModel, MarkdownModel
from .serializers import ColorModelSerializer, MarkdownModelSerializer


class ColorModelViewSet(viewsets.ModelViewSet):
    queryset = ColorModel.objects.all()
    serializer_class = ColorModelSerializer
    permission_classes = [AllowAny,]


class MarkdownModelViewSet(viewsets.ModelViewSet):
    queryset = MarkdownModel.objects.all()
    serializer_class = MarkdownModelSerializer
    permission_classes = [AllowAny,]
