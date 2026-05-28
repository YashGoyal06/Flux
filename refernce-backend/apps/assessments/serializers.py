from rest_framework import serializers
from .models import CodingQuestion, CandidateAssessment
from candidates.serializers import CandidateSerializer
from jobs.serializers import JobSerializer

class CodingQuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = CodingQuestion
        fields = ['id', 'title', 'difficulty', 'description', 'starter_code', 'test_cases', 'time_limit', 'memory_limit']
        # Hide hidden test cases in public serialization if needed, or serialize a filtered structure
        # For simplification, we'll serialize all but flag or filter test cases in Candidate views

class CandidateAssessmentSerializer(serializers.ModelSerializer):
    candidate = CandidateSerializer(read_only=True)
    job = JobSerializer(read_only=True)
    questions = CodingQuestionSerializer(many=True, read_only=True)
    time_remaining_seconds = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = CandidateAssessment
        fields = [
            'id', 'token', 'candidate', 'job', 'questions', 'expires_at', 
            'started_at', 'completed_at', 'duration_minutes', 'submissions', 
            'results', 'time_remaining_seconds'
        ]
        read_only_fields = ['id', 'token', 'expires_at']

    def get_time_remaining_seconds(self, obj):
        if not obj.started_at or obj.completed_at:
            return obj.duration_minutes * 60
        elapsed_seconds = (timezone_now() - obj.started_at).total_seconds()
        allowed_seconds = obj.duration_minutes * 60
        remaining = allowed_seconds - elapsed_seconds
        return max(0, int(remaining))

from django.utils import timezone
def timezone_now():
    return timezone.now()

class RunCodeSerializer(serializers.Serializer):
    question_id = serializers.IntegerField()
    code = serializers.CharField()
    language = serializers.CharField()
    stdin = serializers.CharField(required=False, allow_blank=True)
    expected_output = serializers.CharField(required=False, allow_blank=True)

class SubmitCodeSerializer(serializers.Serializer):
    question_id = serializers.IntegerField()
    code = serializers.CharField()
    language = serializers.CharField()


class ExecuteCodeSerializer(serializers.Serializer):
    code = serializers.CharField()
    language = serializers.CharField()
    stdin = serializers.CharField(required=False, allow_blank=True)
    expected_output = serializers.CharField(required=False, allow_blank=True)
