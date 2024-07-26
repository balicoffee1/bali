from rest_framework import serializers

from music_api.models import Music


class MusicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Music
        fields = ('title', 'author', 'track_id', 'cover_image_url', 'song')
