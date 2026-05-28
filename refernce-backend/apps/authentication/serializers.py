from rest_framework import serializers
from django.contrib.auth.models import User
import hashlib
from companies.models import RecruiterToken, RecruiterProfile, Company
from django.utils import timezone

class RecruiterLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    token = serializers.CharField(max_length=255) # Can be a security token or a user password

    def validate(self, data):
        email = data.get('email', '').strip().lower()
        password_or_token = data.get('token', '').strip()
        print(f"[DEBUG] VALIDATING: email={email}")

        # Check if a recruiter user account already exists
        user = User.objects.filter(email__iexact=email).first()
        if user:
            # If the user exists, they must log in using their password
            if user.check_password(password_or_token):
                try:
                    rec_token = RecruiterToken.objects.get(email__iexact=email, is_revoked=False)
                except RecruiterToken.DoesNotExist:
                    raise serializers.ValidationError("Recruiter account is not fully provisioned.")
                
                data['user'] = user
                data['recruiter_token'] = rec_token
                data['setup_required'] = False
                return data
            else:
                raise serializers.ValidationError("Invalid email, password, or security token.")

        # If no user account exists, authenticate using the one-time security token
        token_hash = hashlib.sha256(password_or_token.encode('utf-8')).hexdigest()
        try:
            rec_token = RecruiterToken.objects.get(email__iexact=email, token_hash=token_hash, is_used=False, is_revoked=False)
        except RecruiterToken.DoesNotExist:
            raise serializers.ValidationError("Invalid email, password, or security token.")

        if rec_token.has_expired():
            raise serializers.ValidationError("This invitation token has expired (72 hours limit).")

        data['recruiter_token'] = rec_token
        data['setup_required'] = True
        return data

class RecruiterProfileSetupSerializer(serializers.Serializer):
    email = serializers.EmailField()
    token = serializers.CharField(max_length=255)
    password = serializers.CharField(max_length=128)
    confirm_password = serializers.CharField(max_length=128)
    full_name = serializers.CharField(max_length=255)
    job_title = serializers.CharField(max_length=255)
    department = serializers.CharField(max_length=100)
    phone_number = serializers.CharField(max_length=50)
    linkedin_url = serializers.URLField(required=False, allow_blank=True, allow_null=True)
    specialization_areas = serializers.ListField(child=serializers.CharField(max_length=100))
    years_of_experience = serializers.CharField(max_length=50)
    bio = serializers.CharField(max_length=500, required=False, allow_blank=True, allow_null=True)
    preferred_timezone = serializers.CharField(max_length=100)
    notification_preferences = serializers.JSONField(required=False, default=dict)
    photo_url = serializers.URLField(required=False, allow_blank=True, allow_null=True)
    passing_ats_score = serializers.IntegerField(required=False, default=70)

    def validate(self, data):
        email = data.get('email', '').strip().lower()
        token = data.get('token', '').strip()
        password = data.get('password')
        confirm_password = data.get('confirm_password')

        if not password or len(password) < 8:
            raise serializers.ValidationError({"password": "Password must be at least 8 characters long."})

        if password != confirm_password:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})

        # Hash token and look up
        token_hash = hashlib.sha256(token.encode('utf-8')).hexdigest()

        try:
            rec_token = RecruiterToken.objects.get(email__iexact=email, token_hash=token_hash)
        except RecruiterToken.DoesNotExist:
            raise serializers.ValidationError("Invalid token validation.")

        if rec_token.is_revoked:
            raise serializers.ValidationError("Token has been revoked.")

        if rec_token.is_used:
            raise serializers.ValidationError("This setup token has already been consumed.")

        if rec_token.has_expired():
            raise serializers.ValidationError("Token has expired.")

        data['recruiter_token'] = rec_token
        return data
