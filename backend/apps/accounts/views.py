import secrets

import requests
from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import Meeting, UserAccount
from .serializers import MeetingSerializer


def _public_user(user):
    return {
        "name": user.name,
        "username": user.username,
        "profilePicture": user.profile_picture,
    }


def _issue_token(user):
    user.token = secrets.token_hex(20)
    user.save(update_fields=["token", "updated_at"])
    return user.token


def _get_user_by_token(token):
    if not token:
        return None
    return UserAccount.objects.filter(token=token).first()


@api_view(["POST"])
def register(request):
    name = request.data.get("name")
    username = request.data.get("username")
    password = request.data.get("password")

    if not name or not username or not password:
        return Response({"message": "Please Provide"}, status=status.HTTP_400_BAD_REQUEST)

    if UserAccount.objects.filter(username=username).exists():
        return Response({"message": "User already exists"}, status=status.HTTP_302_FOUND)

    UserAccount.objects.create(
        name=name,
        username=username,
        password=make_password(password),
    )

    return Response({"message": "User Registered"}, status=status.HTTP_201_CREATED)


@api_view(["POST"])
def login(request):
    username = request.data.get("username")
    password = request.data.get("password")

    if not username or not password:
        return Response({"message": "Please Provide"}, status=status.HTTP_400_BAD_REQUEST)

    user = UserAccount.objects.filter(username=username).first()
    if not user:
        return Response({"message": "User Not Found"}, status=status.HTTP_404_NOT_FOUND)

    if not check_password(password, user.password):
        return Response({"message": "Invalid Username or password"}, status=status.HTTP_401_UNAUTHORIZED)

    token = _issue_token(user)
    return Response({"token": token, "user": _public_user(user)}, status=status.HTTP_200_OK)


@api_view(["GET"])
def get_user_history(request):
    user = _get_user_by_token(request.query_params.get("token"))
    if not user:
        return Response({"message": "User not found"}, status=status.HTTP_404_NOT_FOUND)

    return Response(MeetingSerializer(user.meetings.all(), many=True).data, status=status.HTTP_200_OK)


@api_view(["POST"])
def add_to_history(request):
    user = _get_user_by_token(request.data.get("token"))
    if not user:
        return Response({"message": "User not found"}, status=status.HTTP_404_NOT_FOUND)

    meeting_code = request.data.get("meeting_code")
    if not meeting_code:
        return Response({"message": "meeting_code is required"}, status=status.HTTP_400_BAD_REQUEST)

    Meeting.objects.create(user=user, meeting_code=meeting_code)
    return Response({"message": "Added code to history"}, status=status.HTTP_201_CREATED)


@api_view(["DELETE"])
def delete_meeting(request, meeting_code):
    user = _get_user_by_token(request.query_params.get("token"))
    if not user:
        return Response({"message": "User not found"}, status=status.HTTP_404_NOT_FOUND)

    deleted_count, _ = Meeting.objects.filter(user=user, meeting_code=meeting_code).delete()
    if deleted_count == 0:
        return Response({"message": "Meeting not found"}, status=status.HTTP_404_NOT_FOUND)

    return Response({"message": "Meeting deleted successfully"}, status=status.HTTP_200_OK)


@api_view(["DELETE"])
def delete_all_meetings(request):
    user = _get_user_by_token(request.query_params.get("token"))
    if not user:
        return Response({"message": "User not found"}, status=status.HTTP_404_NOT_FOUND)

    Meeting.objects.filter(user=user).delete()
    return Response({"message": "All meetings deleted successfully"}, status=status.HTTP_200_OK)


@api_view(["POST"])
def google_login(request):
    credential = request.data.get("token")
    if not credential:
        return Response({"message": "Token is required"}, status=status.HTTP_400_BAD_REQUEST)

    if not settings.GOOGLE_CLIENT_ID:
        return Response({"message": "Google login is not configured"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    try:
        payload = id_token.verify_oauth2_token(
            credential,
            google_requests.Request(),
            settings.GOOGLE_CLIENT_ID,
        )
    except ValueError:
        return Response({"message": "Invalid Google token. Please try again."}, status=status.HTTP_401_UNAUTHORIZED)

    email = payload.get("email")
    google_id = payload.get("sub")
    name = payload.get("name") or email
    picture = payload.get("picture")

    user = UserAccount.objects.filter(username=email).first()
    if not user:
        user = UserAccount.objects.create(
            name=name,
            username=email,
            password=make_password(secrets.token_hex(16)),
            google_id=google_id,
            profile_picture=picture,
        )
    else:
        user.google_id = user.google_id or google_id
        user.profile_picture = picture or user.profile_picture
        user.name = user.name or name
        user.save(update_fields=["google_id", "profile_picture", "name", "updated_at"])

    token = _issue_token(user)
    return Response({"token": token, "user": _public_user(user)}, status=status.HTTP_200_OK)


@api_view(["POST"])
def supabase_login(request):
    access_token = request.data.get("access_token")
    if not access_token:
        return Response({"message": "access_token is required"}, status=status.HTTP_400_BAD_REQUEST)

    if not settings.SUPABASE_URL or not settings.SUPABASE_ANON_KEY:
        return Response({"message": "Supabase auth is not configured"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    try:
        supabase_response = requests.get(
            f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/user",
            headers={
                "apikey": settings.SUPABASE_ANON_KEY,
                "Authorization": f"Bearer {access_token}",
            },
            timeout=10,
        )
    except requests.RequestException:
        return Response({"message": "Could not verify Supabase session"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    if supabase_response.status_code != 200:
        return Response({"message": "Invalid Supabase session"}, status=status.HTTP_401_UNAUTHORIZED)

    supabase_user = supabase_response.json()
    email = supabase_user.get("email")
    metadata = supabase_user.get("user_metadata") or {}

    if not email:
        return Response({"message": "Supabase user email is missing"}, status=status.HTTP_400_BAD_REQUEST)

    name = metadata.get("full_name") or metadata.get("name") or email
    picture = metadata.get("avatar_url") or metadata.get("picture")
    provider_id = supabase_user.get("id")

    user = UserAccount.objects.filter(username=email).first()
    if not user:
        user = UserAccount.objects.create(
            name=name,
            username=email,
            password=make_password(secrets.token_hex(16)),
            google_id=provider_id,
            profile_picture=picture,
        )
    else:
        user.name = name or user.name
        user.google_id = user.google_id or provider_id
        user.profile_picture = picture or user.profile_picture
        user.save(update_fields=["name", "google_id", "profile_picture", "updated_at"])

    token = _issue_token(user)
    return Response({"token": token, "user": _public_user(user)}, status=status.HTTP_200_OK)
