from django.urls import path

from . import views


urlpatterns = [
    path("login", views.login),
    path("register", views.register),
    path("add_to_activity", views.add_to_history),
    path("get_all_activity", views.get_user_history),
    path("delete_meeting/<str:meeting_code>", views.delete_meeting),
    path("delete_all_meetings", views.delete_all_meetings),
]
