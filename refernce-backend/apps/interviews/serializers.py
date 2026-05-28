from rest_framework import serializers
from .models import InterviewSession
from candidates.serializers import CandidateSerializer
from jobs.serializers import JobSerializer

class InterviewSessionSerializer(serializers.ModelSerializer):
    candidate = CandidateSerializer(read_only=True)
    job = JobSerializer(read_only=True)

    class Meta:
        model = InterviewSession
        fields = ['id', 'room_id', 'candidate', 'job', 'scheduled_at', 'completed_at', 'recording_url', 'private_notes', 'feedback', 'questions', 'created_at']
        read_only_fields = ['id', 'room_id', 'created_at']


    def create(self, validated_data):
        candidate_id = self.context['request'].data.get('candidate_id')
        job_id = self.context['request'].data.get('job_id')

        from candidates.models import Candidate
        from jobs.models import Job

        candidate = Candidate.objects.get(id=candidate_id)
        job = Job.objects.get(id=job_id)
        company = job.company

        return InterviewSession.objects.create(
            company=company,
            candidate=candidate,
            job=job,
            **validated_data
        )
