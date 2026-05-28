from rest_framework import serializers
from .models import Candidate, Application
from jobs.models import Job
from .parser import parse_resume
import os
import uuid
import time
import tempfile
import requests as http_requests
import jwt
from django.conf import settings
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


def upload_file_to_supabase(file_obj, bucket_name="resumes"):
    """Upload a file to Supabase Storage and return the public URL."""
    ext = os.path.splitext(file_obj.name)[1]
    file_name = f"{uuid.uuid4()}{ext}"

    jwt_secret = settings.SUPABASE_JWT_SECRET
    decoded_secret = jwt_secret.encode('utf-8') if isinstance(jwt_secret, str) else jwt_secret

    payload = {
        "role": "service_role",
        "iss": "supabase",
        "iat": int(time.time()),
        "exp": int(time.time() + 3600)
    }
    token = jwt.encode(payload, decoded_secret, algorithm="HS256")
    if isinstance(token, bytes):
        token = token.decode('utf-8')

    # Ensure the bucket exists
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    bucket_check_url = f"{settings.SUPABASE_URL}/storage/v1/bucket/{bucket_name}"
    check_res = http_requests.get(bucket_check_url, headers=headers)

    if check_res.status_code != 200:
        create_bucket_url = f"{settings.SUPABASE_URL}/storage/v1/bucket"
        body = {"id": bucket_name, "name": bucket_name, "public": True}
        http_requests.post(create_bucket_url, headers=headers, json=body)

    # Upload file
    upload_headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": file_obj.content_type or "application/octet-stream"
    }
    upload_url = f"{settings.SUPABASE_URL}/storage/v1/object/{bucket_name}/{file_name}"

    file_data = file_obj.read()
    res = http_requests.post(upload_url, headers=upload_headers, data=file_data)

    if res.status_code == 200:
        public_url = f"{settings.SUPABASE_URL}/storage/v1/object/public/{bucket_name}/{file_name}"
        # Reset file position so it can be read again for parsing
        file_obj.seek(0)
        return public_url
    else:
        logger.error(f"Failed to upload to Supabase Storage: {res.status_code} - {res.text}")
        file_obj.seek(0)
        return None


class CandidateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Candidate
        fields = '__all__'

class ApplicationSerializer(serializers.ModelSerializer):
    candidate = CandidateSerializer(read_only=True)
    job_title = serializers.CharField(source='job.title', read_only=True)
    company_name = serializers.CharField(source='company.name', read_only=True)

    class Meta:
        model = Application
        fields = [
            'id', 'job', 'job_title', 'company_name', 'candidate', 'current_stage', 
            'cover_letter', 'resume_file', 'internal_notes', 'status', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class SubmitApplicationSerializer(serializers.Serializer):
    job_id = serializers.IntegerField()
    name = serializers.CharField(max_length=255)
    email = serializers.EmailField()
    phone = serializers.CharField(max_length=50, required=False, allow_blank=True)
    resume = serializers.FileField(required=False, allow_null=True)
    cover_letter = serializers.CharField(required=False, allow_blank=True)

    def validate_job_id(self, value):
        try:
            job = Job.objects.get(id=value, status="Active")
        except Job.DoesNotExist:
            raise serializers.ValidationError("Job posting not found or is closed.")
        if job.deadline and job.deadline < timezone.localdate():
            raise serializers.ValidationError("Job posting deadline has passed.")
        return value

    def create(self, validated_data):
        job_id = validated_data['job_id']
        job = Job.objects.get(id=job_id)
        email = validated_data['email']
        name = validated_data['name']
        phone = validated_data.get('phone', '')
        cover_letter = validated_data.get('cover_letter', '')
        resume_file = validated_data.get('resume')

        # Get or create candidate
        name_parts = name.strip().split(' ', 1)
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else ''

        candidate, created = Candidate.objects.get_or_create(
            email=email,
            defaults={
                'first_name': first_name,
                'last_name': last_name,
                'phone': phone
            }
        )

        # Upload resume to Supabase Storage
        resume_url = ''
        if resume_file:
            resume_url = upload_file_to_supabase(resume_file, bucket_name="resumes")
            if not resume_url:
                resume_url = ''  # Fallback: store empty if upload fails
        else:
            # Re-use existing resume
            # Look in parsed_resume documents first
            if isinstance(candidate.parsed_resume, dict) and 'documents' in candidate.parsed_resume:
                docs = candidate.parsed_resume['documents']
                if isinstance(docs, list) and len(docs) > 0:
                    resume_url = docs[0].get('url', '')
            
            # If not found, look in previous applications
            if not resume_url:
                prev_app = Application.objects.filter(candidate=candidate).exclude(resume_file='').order_by('-created_at').first()
                if prev_app:
                    resume_url = prev_app.resume_file
                    
            if not resume_url:
                raise serializers.ValidationError({"resume": "No resume file was provided, and no existing resume was found on file."})

        # Create application with the Supabase URL
        application = Application.objects.create(
            company=job.company,
            job=job,
            candidate=candidate,
            cover_letter=cover_letter,
            resume_file=resume_url,
            current_stage="Applied",
            status="Active"
        )

        # Parse resume using a temp file (since file is in-memory)
        if resume_file:
            try:
                ext = os.path.splitext(resume_file.name)[1]
                with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                    for chunk in resume_file.chunks():
                        tmp.write(chunk)
                    tmp_path = tmp.name

                parsed_data, confidence = parse_resume(tmp_path)

                # Clean up temp file
                os.unlink(tmp_path)

                # Update candidate details with parsed info
                candidate.parsed_resume = parsed_data
                
                # Calculate job-specific ATS match score
                from .parser import calculate_ats_score
                ats_score = calculate_ats_score(parsed_data, job)
                candidate.confidence_score = ats_score
                
                if parsed_data.get('phone') and not candidate.phone:
                    candidate.phone = parsed_data['phone']
                candidate.save()
            except Exception as e:
                # Keep application active even if parser errors out
                logger.error(f"Error executing resume parser during application submit: {e}")
                # Clean up temp file on error too
                try:
                    if 'tmp_path' in locals():
                        os.unlink(tmp_path)
                except OSError:
                    pass
        else:
            # Re-calculate ATS score using candidate's existing parsed_resume and the new job
            if isinstance(candidate.parsed_resume, dict) and candidate.parsed_resume:
                try:
                    from .parser import calculate_ats_score
                    ats_score = calculate_ats_score(candidate.parsed_resume, job)
                    candidate.confidence_score = ats_score
                    candidate.save()
                except Exception as e:
                    logger.error(f"Error calculating ATS score for existing resume: {e}")

        return application
