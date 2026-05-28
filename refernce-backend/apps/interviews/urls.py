from django.urls import path
from .views import (
    InterviewSessionListCreateView, InterviewSessionDetailView, UpdatePrivateNotesView,
    SubmitFeedbackView, CandidateMyInterviewsView, InterviewQuestionsView,
    InterviewImportPdfView, InterviewImportCodeforcesView
)


urlpatterns = [
    path('', InterviewSessionListCreateView.as_view(), name='interview_list_create'),
    path('my-interviews/', CandidateMyInterviewsView.as_view(), name='my_interviews'),
    path('<str:room_id>/', InterviewSessionDetailView.as_view(), name='interview_detail'),
    path('<str:room_id>/notes/', UpdatePrivateNotesView.as_view(), name='interview_notes'),
    path('<str:room_id>/feedback/', SubmitFeedbackView.as_view(), name='interview_feedback'),
    path('<str:room_id>/questions/', InterviewQuestionsView.as_view(), name='interview_questions'),
    path('<str:room_id>/import-pdf/', InterviewImportPdfView.as_view(), name='interview_import_pdf'),
    path('<str:room_id>/import-codeforces/', InterviewImportCodeforcesView.as_view(), name='interview_import_codeforces'),
]


