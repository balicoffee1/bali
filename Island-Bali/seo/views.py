from rest_framework import viewsets
from .models import ColorModel
from .serializers import ColorModelSerializer
from rest_framework.permissions import AllowAny

class ColorModelViewSet(viewsets.ModelViewSet):
    queryset = ColorModel.objects.all()
    serializer_class = ColorModelSerializer
    permission_classes = [AllowAny,]
