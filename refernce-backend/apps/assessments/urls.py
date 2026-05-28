from django.urls import path
from .views import AssignAssessmentView, CandidateAssessmentSessionView, RunCodeView, SubmitSolutionView, FinishAssessmentView, CodingQuestionsListView, ExecuteCodeView

urlpatterns = [
    path('questions/', CodingQuestionsListView.as_view(), name='coding_questions_list'),
    path('assign/', AssignAssessmentView.as_view(), name='assign_assessment'),
    path('execute/', ExecuteCodeView.as_view(), name='assessment_execute_code'),
    path('session/<uuid:token>/', CandidateAssessmentSessionView.as_view(), name='assessment_session'),
    path('session/<uuid:token>/run/', RunCodeView.as_view(), name='assessment_run_code'),
    path('session/<uuid:token>/submit/', SubmitSolutionView.as_view(), name='assessment_submit_solution'),
    path('session/<uuid:token>/finish/', FinishAssessmentView.as_view(), name='assessment_finish'),
]
