from django.http import JsonResponse
from django.urls import include, path


def health(_request):
    return JsonResponse({"status": "ok", "message": "Server is running"})


urlpatterns = [
    path("health", health),
    path("api/v1/users/", include("apps.accounts.urls")),
    path("api/v1/auth/", include("apps.accounts.auth_urls")),
]
