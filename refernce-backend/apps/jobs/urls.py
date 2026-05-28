from django.urls import path
from .views import JobListCreateView, JobDetailView, PublicJobDetailView

urlpatterns = [
    path('', JobListCreateView.as_view(), name='job_list_create'),
    path('<int:pk>/', JobDetailView.as_view(), name='job_detail'),
    path('public/<int:pk>/', PublicJobDetailView.as_view(), name='public_job_detail'),
]
