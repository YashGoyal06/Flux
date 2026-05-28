from django.urls import path
from .views import RecruiterLoginView, RecruiterProfileSetupView, TestCredentialsListView, PublicFileUploadView, UpdateProfileView

urlpatterns = [
    path('recruiter-login/', RecruiterLoginView.as_view(), name='recruiter_login'),
    path('recruiter-profile-setup/', RecruiterProfileSetupView.as_view(), name='recruiter_profile_setup'),
    path('test-credentials/', TestCredentialsListView.as_view(), name='test_credentials'),
    path('upload-file/', PublicFileUploadView.as_view(), name='public_file_upload'),
    path('update-profile/', UpdateProfileView.as_view(), name='update_profile'),
]
