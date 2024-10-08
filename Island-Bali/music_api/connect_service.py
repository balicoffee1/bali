import os
import random
from typing import Dict, List

from yandex_music import Client

from island_bali import settings
from music_api.models import Music
import requests
import urllib.parse

token: str = 'y0_AgAAAABJVJRMAAG8XgAAAADzGIKC_pMkmWp_QiCWTtjQeHiothhUDxE'
client: Client = Client(token).init()
chart: List[Dict] = client.chart('russia').chart


def get_chart() -> List[Dict]:
    """Получает список песен из русского чарта"""
    chart_data: List[Dict] = []
    for track_info in chart.tracks:
        track_data: Dict = {
            "song_title": track_info["track"]["title"],
            "artist": track_info["track"]["artists"][0]["name"],
            "track_id": track_info["track"]["id"],
            "cover_image_url": track_info['track']['cover_uri']
        }
        chart_data.append(track_data)
    return chart_data


def random_track() -> Dict:
    """Рандомно выбирает трек из чарта"""
    chart_data: List[Dict] = get_chart()
    if not chart_data:
        raise Exception("Чарт пуст")
    return random.choice(chart_data)


def get_track_id() -> int:
    """Получает ID случайного трека"""
    track: Dict = random_track()
    return track["track_id"]


def del_last_download_track():
    # Получаем информацию о последнем скачанном треке из базы данных
    last_track = Music.objects.last()

    if not last_track:
        print("Нет скачанных треков для удаления")
        return

    # Получаем путь к файлу скачанного трека
    track_id = last_track.track_id
    file_path = os.path.join(settings.MEDIA_ROOT, f'track_{track_id}.mp3')

    # Удаляем файл скачанного трека из файловой системы
    if os.path.exists(file_path):
        os.remove(file_path)
        print(f"Файл {file_path} удален")
    else:
        print(f"Файл {file_path} не найден")

    # Удаляем запись о треке из базы данных
    last_track.delete()

    print(f"Трек с ID {track_id} удален из базы данных")


def download_track():
    """Скачивает песню по ID"""
    try:
        del_last_download_track()
        track_id: int = get_track_id()
        track: Client.Track = client.tracks(track_id)[0]
        file_path = f'track_{track_id}.mp3'
        track.download(file_path)
        
        cover_image_url = track.cover_uri
        image_path = cover_image_url[:-2]+"400x400"
        
        # Создать объект Music и сохранить его в базе данных
        music = Music(
            title=track.title,
            author=track.artists[0].name,
            track_id=str(track_id),
            cover_image_url=image_path,
            song=file_path
        )
        music.save()

        print(f'Песня с ID {track_id} '
              f'успешно скачана и сохранена в базе данных')
    except Exception as e:
        print(f'Ошибка: {str(e)}')


