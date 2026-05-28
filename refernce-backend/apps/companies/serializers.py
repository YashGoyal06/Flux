from rest_framework import serializers
from .models import RecruiterProfile, RecruiterToken, Company
from django.contrib.auth.models import User
import secrets
import hashlib
from django.utils import timezone
from datetime import timedelta

class RecruiterProfileSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source='user.email', read_only=True)
    username = serializers.CharField(source='user.username', read_only=True)
    last_login = serializers.DateTimeField(source='user.last_login', read_only=True)

    class Meta:
        model = RecruiterProfile
        fields = [
            'id', 'username', 'email', 'full_name', 'job_title', 'department',
            'phone_number', 'linkedin_url', 'specialization_areas',
            'years_of_experience', 'bio', 'preferred_timezone',
            'notification_preferences', 'photo_url', 'passing_ats_score', 'last_login', 'created_at'
        ]

class RecruiterTokenSerializer(serializers.ModelSerializer):
    class Meta:
        model = RecruiterToken
        fields = ['id', 'email', 'is_used', 'is_revoked', 'created_at', 'expires_at']
        read_only_fields = ['id', 'is_used', 'is_revoked', 'created_at', 'expires_at']

class CreateRecruiterRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        # Enforce official email checks or duplicate checks if needed
        # We can check if a recruiter token already exists for this email
        company = self.context['request'].company
        clean_email = value.strip().lower()
        if RecruiterToken.objects.filter(company=company, email__iexact=clean_email, is_revoked=False, is_used=False, expires_at__gt=timezone.now()).exists():
            raise serializers.ValidationError("An active invitation already exists for this email address.")
        return clean_email

    def create(self, validated_data):
        email = validated_data['email']
        company = self.context['request'].company

        # Generate cryptographically secure 64-char hex token (CSPRNG, 256 bits of entropy)
        raw_token = secrets.token_hex(32) # 32 bytes = 64 hex chars
        
        # Hash it using SHA-256 for secure storage
        token_hash = hashlib.sha256(raw_token.encode('utf-8')).hexdigest()

        # Tokens expire in 72 hours by default
        expires_at = timezone.now() + timedelta(hours=72)

        recruiter_token = RecruiterToken.objects.create(
            company=company,
            email=email,
            token_hash=token_hash,
            expires_at=expires_at
        )

        return recruiter_token, raw_token
