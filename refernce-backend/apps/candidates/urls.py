from django.urls import path
from .views import (
    CandidatePipelineListView, ApplicationDetailView, UpdatePipelineStageView,
    AddInternalNoteView, PublicApplyView, CandidateMyApplicationsView,
    CandidateProfileUpdateView, CandidateTrackLoginView
)


urlpatterns = [
    path('', CandidatePipelineListView.as_view(), name='candidate_pipeline_list'),
    path('my-applications/', CandidateMyApplicationsView.as_view(), name='my_applications'),
    path('profile/', CandidateProfileUpdateView.as_view(), name='candidate_profile_update'),
    path('track-login/', CandidateTrackLoginView.as_view(), name='track_login'),
    path('<int:pk>/', ApplicationDetailView.as_view(), name='application_detail'),
    path('<int:pk>/stage/', UpdatePipelineStageView.as_view(), name='update_stage'),
    path('<int:pk>/notes/', AddInternalNoteView.as_view(), name='add_note'),
    path('public/apply/', PublicApplyView.as_view(), name='public_apply'),
]


