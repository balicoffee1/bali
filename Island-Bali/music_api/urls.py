from django.urls import path# from .views import AudioFileViewfrom .views import DownloadMusicView, get_audiourlpatterns = [    # path('', AudioFileView.as_view()),    path('song_day/', get_audio),    path('listen_song/', DownloadMusicView.as_view(), name='download-music'),]