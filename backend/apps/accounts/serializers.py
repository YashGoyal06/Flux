from rest_framework import serializers

from .models import Meeting


class MeetingSerializer(serializers.ModelSerializer):
    user_id = serializers.CharField(source="user.username", read_only=True)
    meetingCode = serializers.CharField(source="meeting_code", read_only=True)

    class Meta:
        model = Meeting
        fields = ["id", "user_id", "meetingCode", "date"]
