from django.urls import path

from . import views


urlpatterns = [
    path("google", views.google_login),
    path("supabase", views.supabase_login),
]
