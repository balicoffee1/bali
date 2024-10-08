from django.http import FileResponse
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.decorators import permission_classes
from rest_framework import permissions

from music_api.models import Music
from music_api.serializers import MusicSerializer
from music_api.connect_service import download_track

TAGS_MUSIC = ['Музыка']


@swagger_auto_schema(
    method='get',
    operation_description="Метод для получения данных о песне дня",
    responses={200: "Good", 400: "Bad Request"},
    tags=TAGS_MUSIC,
    operation_id="Получить песню дня"
)
@permission_classes([permissions.AllowAny])
@api_view(['GET'])
def get_audio(request):
    download_track()
    latest_song = Music.objects.latest('id')
    serializers = MusicSerializer(latest_song)
    return Response(serializers.data, status=status.HTTP_200_OK)


class DownloadMusicView(APIView):
    @swagger_auto_schema(
        operation_description="Метод для прослушивания музыки",
        responses={200: "Good", 400: "Bad Request"},
        tags=TAGS_MUSIC,
        operation_id="Прослушать музыку"
    )
    @permission_classes([permissions.AllowAny])
    def get(self, request, *args, **kwargs):
        try:
            music = Music.objects.latest("id")
            response = FileResponse(open(music.song.path, 'rb'))
            response['Content-Disposition'] = (f'attachment; '
                                               f'filename="{music.title}.mp3"')
            return response
        except Music.DoesNotExist:
            return Response(
                {"message": "Музыка с указанным ID не найдена."},
                status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            error_message = f"Ошибка при загрузке песни: {str(e)}"
            return Response(
                {"message": error_message},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR)
