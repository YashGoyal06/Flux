from rest_framework import serializers
from .models import Job
from django.utils import timezone

class JobSerializer(serializers.ModelSerializer):
    days_open = serializers.ReadOnlyField()
    applicants_count = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Job
        fields = [
            'id', 'title', 'department', 'location', 'type', 'priority', 
            'status', 'description', 'requirements', 'application_form_schema', 
            'pipeline_stages', 'created_at', 'deadline', 'days_open', 'applicants_count'
        ]
        read_only_fields = ['id', 'created_at']

    def get_applicants_count(self, obj):
        # We'll link this to candidates app later
        # Return count of applications linked to this job
        if hasattr(obj, 'applications'):
            return obj.applications.count()
        return 0

    def create(self, validated_data):
        company = self.context['request'].company
        user = self.context['request'].user
        
        # Add default pipeline stages if not specified
        if not validated_data.get('pipeline_stages'):
            validated_data['pipeline_stages'] = ["Applied", "Screening", "Coding Round", "Interview", "Offer", "Hired", "Rejected"]
            
        # Add default application form schema if not specified
        if not validated_data.get('application_form_schema'):
            validated_data['application_form_schema'] = {
                "name": {"required": True, "type": "text"},
                "email": {"required": True, "type": "email"},
                "phone": {"required": True, "type": "tel"},
                "resume": {"required": True, "type": "file"},
                "cover_letter": {"required": False, "type": "textarea"}
            }
            
        return Job.objects.create(company=company, created_by=user, **validated_data)
