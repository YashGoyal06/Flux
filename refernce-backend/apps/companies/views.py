from django.shortcuts import render
from rest_framework import status, views, permissions
from rest_framework.response import Response
from .models import RecruiterProfile, RecruiterToken
from .serializers import RecruiterProfileSerializer, RecruiterTokenSerializer, CreateRecruiterRequestSerializer
from django.utils import timezone
from datetime import timedelta
import secrets
import hashlib

class RecruiterManagementView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        company = request.company
        if not company:
            return Response({"detail": "Company context missing."}, status=status.HTTP_400_BAD_REQUEST)

        # Active profiles
        profiles = RecruiterProfile.objects.filter(company=company)
        profile_serializer = RecruiterProfileSerializer(profiles, many=True)

        # Pending / unused invitation tokens
        pending_tokens = RecruiterToken.objects.filter(
            company=company, 
            is_used=False, 
            is_revoked=False,
            expires_at__gt=timezone.now()
        )
        token_serializer = RecruiterTokenSerializer(pending_tokens, many=True)

        return Response({
            "active_recruiters": profile_serializer.data,
            "pending_invites": token_serializer.data
        }, status=status.HTTP_200_OK)

    def post(self, request):
        company = request.company
        if not company:
            return Response({"detail": "Company context missing."}, status=status.HTTP_400_BAD_REQUEST)

        serializer = CreateRecruiterRequestSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            rec_token, raw_token = serializer.save()
            return Response({
                "message": "Recruiter token generated successfully.",
                "email": rec_token.email,
                "raw_token": raw_token,  # Shift responsibility to client to display ONCE
                "expires_at": rec_token.expires_at,
                "token_info": RecruiterTokenSerializer(rec_token).data
            }, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class RevokeRecruiterView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        company = request.company
        # Revoke a token
        token = RecruiterToken.objects.filter(company=company, id=pk).first()
        if token:
            token.is_revoked = True
            token.save()
            
            # Deactivate corresponding user account if exists
            profile = RecruiterProfile.objects.filter(company=company, user__email__iexact=token.email).first()
            if profile:
                profile.user.is_active = False
                profile.user.save()
                
            return Response({"message": "Recruiter invitation/access revoked successfully."}, status=status.HTTP_200_OK)

        # Revoke directly via profile id
        profile = RecruiterProfile.objects.filter(company=company, id=pk).first()
        if profile:
            profile.user.is_active = False
            profile.user.save()
            
            # Also revoke any tokens for this email
            RecruiterToken.objects.filter(company=company, email__iexact=profile.user.email).update(is_revoked=True)
            return Response({"message": "Recruiter profile deactivated successfully."}, status=status.HTTP_200_OK)

        return Response({"detail": "Recruiter not found."}, status=status.HTTP_404_NOT_FOUND)

class RegenerateRecruiterTokenView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        company = request.company
        email = request.data.get('email')
        if not email:
            return Response({"email": ["This field is required."]}, status=status.HTTP_400_BAD_REQUEST)

        clean_email = email.strip().lower()

        # Revoke previous active tokens for this email
        RecruiterToken.objects.filter(company=company, email__iexact=clean_email, is_used=False).update(is_revoked=True)

        # Generate a new token
        raw_token = secrets.token_hex(32)
        token_hash = hashlib.sha256(raw_token.encode('utf-8')).hexdigest()
        expires_at = timezone.now() + timedelta(hours=72)

        new_token = RecruiterToken.objects.create(
            company=company,
            email=clean_email,
            token_hash=token_hash,
            expires_at=expires_at
        )

        return Response({
            "message": "Recruiter token regenerated successfully.",
            "email": email,
            "raw_token": raw_token,
            "expires_at": expires_at
        }, status=status.HTTP_200_OK)
