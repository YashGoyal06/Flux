from rest_framework import generics, permissions, status
from rest_framework.response import Response
from django.db.models import Q
from django.utils import timezone
from .models import Job
from .serializers import JobSerializer


def public_open_jobs():
    today = timezone.localdate()
    return Job.objects.filter(status="Active").filter(
        Q(deadline__isnull=True) | Q(deadline__gte=today)
    )

class JobListCreateView(generics.ListCreateAPIView):
    serializer_class = JobSerializer

    def get_permissions(self):
        if self.request.method == 'GET':
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        # Force DRF authentication to evaluate
        is_authenticated = self.request.user.is_authenticated
        company = getattr(self.request, 'company', None)
        
        if not company and is_authenticated:
            from companies.models import CompanyAdminProfile, RecruiterProfile
            admin_profile = CompanyAdminProfile.objects.filter(user=self.request.user).first()
            if admin_profile:
                company = admin_profile.company
            else:
                recruiter_profile = RecruiterProfile.objects.filter(user=self.request.user).first()
                if recruiter_profile:
                    company = recruiter_profile.company

        if company:
            queryset = Job.objects.filter(company=company).order_by('-created_at')
            from companies.models import RecruiterProfile, CompanyAdminProfile
            is_admin = CompanyAdminProfile.objects.filter(user=self.request.user).exists()
            is_recruiter = RecruiterProfile.objects.filter(user=self.request.user).exists()
            if is_recruiter and not is_admin:
                queryset = queryset.filter(created_by=self.request.user)
            return queryset
        # Fallback for candidates/public to see active jobs
        return public_open_jobs().order_by('-created_at')

class JobDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = JobSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        company = self.request.company
        if not company:
            return Job.objects.none()
        return Job.objects.filter(company=company)

class PublicJobDetailView(generics.RetrieveAPIView):
    serializer_class = JobSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        return public_open_jobs()
