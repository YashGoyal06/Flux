from django.urls import path
from .views import RecruiterManagementView, RevokeRecruiterView, RegenerateRecruiterTokenView

urlpatterns = [
    path('recruiters/', RecruiterManagementView.as_view(), name='recruiter_management'),
    path('recruiters/<int:pk>/revoke/', RevokeRecruiterView.as_view(), name='revoke_recruiter'),
    path('recruiters/regenerate-token/', RegenerateRecruiterTokenView.as_view(), name='regenerate_recruiter_token'),
]
