from django.shortcuts import render
from rest_framework import status, views
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.contrib.auth.models import User
from rest_framework_simplejwt.tokens import RefreshToken
from companies.models import RecruiterProfile, RecruiterToken
from .serializers import RecruiterLoginSerializer, RecruiterProfileSetupSerializer

def get_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }

class RecruiterLoginView(views.APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        print(f"[DEBUG] RECRUITER LOGIN POST REQUEST DATA: {request.data}")
        serializer = RecruiterLoginSerializer(data=request.data)
        if serializer.is_valid():
            if serializer.validated_data.get('setup_required', False):
                rec_token = serializer.validated_data['recruiter_token']
                return Response({
                    'setup_required': True,
                    'message': 'Token verified. Profile setup is required.',
                    'email': rec_token.email
                }, status=status.HTTP_200_OK)
            
            user = serializer.validated_data['user']
            rec_token = serializer.validated_data['recruiter_token']
            profile = RecruiterProfile.objects.filter(company=rec_token.company, user=user).first()
            if not profile:
                rec_token.is_used = False
                rec_token.save()
                return Response({
                    'setup_required': True,
                    'message': 'Profile setup not found. Setup is required.',
                    'email': rec_token.email
                }, status=status.HTTP_200_OK)

            tokens = get_tokens_for_user(user)
            from django.contrib.auth.models import update_last_login
            update_last_login(None, user)
            return Response({
                'setup_required': False,
                'tokens': tokens,
                'user': {
                    'email': profile.user.email,
                    'full_name': profile.full_name,
                    'role': 'recruiter',
                    'job_title': profile.job_title,
                    'company_name': rec_token.company.name,
                    'photo_url': profile.photo_url,
                    'passing_ats_score': profile.passing_ats_score
                }
            }, status=status.HTTP_200_OK)
            
        print(f"[DEBUG] RECRUITER LOGIN SERIALIZER ERRORS: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class RecruiterProfileSetupView(views.APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RecruiterProfileSetupSerializer(data=request.data)
        if serializer.is_valid():
            data = serializer.validated_data
            rec_token = data['recruiter_token']
            
            # Create standard password Django user using custom password
            username = f"recruiter_{rec_token.id}_{User.objects.count() + 1}"
            user = User.objects.create_user(
                username=username,
                email=rec_token.email,
                password=data['password']
            )
            # Split full name for first/last name fields
            name_parts = data['full_name'].split(' ', 1)
            user.first_name = name_parts[0]
            if len(name_parts) > 1:
                user.last_name = name_parts[1]
            user.save()

            # Create recruiter profile
            profile = RecruiterProfile.objects.create(
                company=rec_token.company,
                user=user,
                full_name=data['full_name'],
                job_title=data['job_title'],
                department=data['department'],
                phone_number=data['phone_number'],
                linkedin_url=data.get('linkedin_url'),
                specialization_areas=data.get('specialization_areas', []),
                years_of_experience=data['years_of_experience'],
                bio=data.get('bio'),
                preferred_timezone=data['preferred_timezone'],
                notification_preferences=data.get('notification_preferences', {}),
                photo_url=data.get('photo_url'),
                passing_ats_score=data.get('passing_ats_score', 70)
            )

            # Consume the token
            rec_token.is_used = True
            rec_token.save()

            tokens = get_tokens_for_user(user)
            from django.contrib.auth.models import update_last_login
            update_last_login(None, user)
            return Response({
                'tokens': tokens,
                'user': {
                    'email': user.email,
                    'full_name': profile.full_name,
                    'role': 'recruiter',
                    'job_title': profile.job_title,
                    'company_name': rec_token.company.name,
                    'photo_url': profile.photo_url,
                    'passing_ats_score': profile.passing_ats_score
                }
            }, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

from .models import TestCredential

class TestCredentialsListView(views.APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        credentials = TestCredential.objects.all()
        
        # Diagnostic check
        import os
        env_supabase_url = os.environ.get('SUPABASE_URL', '')
        env_supabase_secret = os.environ.get('SUPABASE_JWT_SECRET', '')
        
        diagnostic = {
            "settings_supabase_url": settings.SUPABASE_URL,
            "settings_supabase_secret_len": len(settings.SUPABASE_JWT_SECRET) if hasattr(settings, 'SUPABASE_JWT_SECRET') else 0,
            "settings_supabase_secret_matches_default": (settings.SUPABASE_JWT_SECRET == 'kcwYMVIO/tp2KTwydJqHc7XnsnvIoYBGVe3LGvl7BAEVIZi25FmsFo70uaRRjmxwBIRYJl5qGX1nJYSJwD5Thw==') if hasattr(settings, 'SUPABASE_JWT_SECRET') else False,
            "env_supabase_url": env_supabase_url,
            "env_supabase_secret_len": len(env_supabase_secret) if env_supabase_secret else 0,
            "env_supabase_secret_value_start": env_supabase_secret[:10] if env_supabase_secret else None,
        }
        
        data = {
            "credentials": [
                {
                    "role": cred.role,
                    "label": cred.label,
                    "email": cred.email,
                    "password": cred.password
                }
                for cred in credentials
            ],
            "diagnostic": diagnostic
        }
        return Response(data, status=status.HTTP_200_OK)


import jwt
import requests
import uuid
import os
import time
from django.conf import settings
from rest_framework.permissions import IsAuthenticated
from companies.models import CompanyAdminProfile

class PublicFileUploadView(views.APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        uploaded_file = request.FILES.get('file')
        if not uploaded_file:
            return Response({"error": "No file uploaded."}, status=status.HTTP_400_BAD_REQUEST)
            
        bucket_name = request.data.get('bucket', 'avatars')
        
        # Generate random unique filename
        ext = os.path.splitext(uploaded_file.name)[1]
        file_name = f"{uuid.uuid4()}{ext}"
        
        try:
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
            
            # 1. Ensure the bucket exists or create it
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            bucket_check_url = f"{settings.SUPABASE_URL}/storage/v1/bucket/{bucket_name}"
            check_res = requests.get(bucket_check_url, headers=headers)
            
            if check_res.status_code != 200:
                create_bucket_url = f"{settings.SUPABASE_URL}/storage/v1/bucket"
                body = {"id": bucket_name, "name": bucket_name, "public": True}
                requests.post(create_bucket_url, headers=headers, json=body)
                
            # 2. Upload file
            upload_headers = {
                "Authorization": f"Bearer {token}",
            }
            upload_url = f"{settings.SUPABASE_URL}/storage/v1/object/{bucket_name}/{file_name}"
            
            file_data = uploaded_file.read()
            content_type = uploaded_file.content_type or "application/octet-stream"
            upload_headers["Content-Type"] = content_type
            
            res = requests.post(upload_url, headers=upload_headers, data=file_data)
            
            if res.status_code == 200:
                public_url = f"{settings.SUPABASE_URL}/storage/v1/object/public/{bucket_name}/{file_name}"
                return Response({"url": public_url}, status=status.HTTP_200_OK)
            else:
                return Response({
                    "error": "Failed to upload file to storage.", 
                    "details": res.text, 
                    "status_code": res.status_code
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class UpdateProfileView(views.APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request):
        admin_profile = CompanyAdminProfile.objects.filter(user=request.user).first()
        if admin_profile:
            photo_url = request.data.get('photo_url')
            if photo_url is not None:
                admin_profile.photo_url = photo_url
                admin_profile.save()
            return Response({
                "message": "Admin profile updated successfully.",
                "user": {
                    "email": request.user.email,
                    "full_name": request.user.first_name + " " + request.user.last_name,
                    "role": "admin",
                    "photo_url": admin_profile.photo_url
                }
            }, status=status.HTTP_200_OK)
            
        recruiter_profile = RecruiterProfile.objects.filter(user=request.user).first()
        if recruiter_profile:
            photo_url = request.data.get('photo_url')
            passing_ats_score = request.data.get('passing_ats_score')
            full_name = request.data.get('full_name')
            job_title = request.data.get('job_title')
            
            if photo_url is not None:
                recruiter_profile.photo_url = photo_url
            if passing_ats_score is not None:
                recruiter_profile.passing_ats_score = int(passing_ats_score)
            if full_name is not None:
                recruiter_profile.full_name = full_name
            if job_title is not None:
                recruiter_profile.job_title = job_title
                
            recruiter_profile.save()
            return Response({
                "message": "Recruiter profile updated successfully.",
                "user": {
                    "email": recruiter_profile.user.email,
                    "full_name": recruiter_profile.full_name,
                    "role": "recruiter",
                    "job_title": recruiter_profile.job_title,
                    "company_name": recruiter_profile.company.name,
                    "photo_url": recruiter_profile.photo_url,
                    "passing_ats_score": recruiter_profile.passing_ats_score
                }
            }, status=status.HTTP_200_OK)
            
        return Response({"error": "Profile not found."}, status=status.HTTP_404_NOT_FOUND)

