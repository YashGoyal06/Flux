from rest_framework import generics, permissions, status, views
from rest_framework.response import Response
from .models import Candidate, Application
from .serializers import ApplicationSerializer, SubmitApplicationSerializer, CandidateSerializer
from django.utils import timezone
import os
import tempfile
import requests
import logging

logger = logging.getLogger(__name__)

def get_request_company(request):
    company = getattr(request, 'company', None)
    if not company and request.user and request.user.is_authenticated:
        from companies.models import CompanyAdminProfile, RecruiterProfile
        admin_profile = CompanyAdminProfile.objects.filter(user=request.user).first()
        if admin_profile:
            company = admin_profile.company
        else:
            recruiter_profile = RecruiterProfile.objects.filter(user=request.user).first()
            if recruiter_profile:
                company = recruiter_profile.company
    return company

class CandidatePipelineListView(generics.ListAPIView):
    serializer_class = ApplicationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Force DRF authentication to evaluate
        if not self.request.user.is_authenticated:
            return Application.objects.none()
            
        company = get_request_company(self.request)
        if not company:
            return Application.objects.none()
            
        queryset = Application.objects.filter(company=company).order_by('-created_at')
        
        # Filter for recruiters who are not admins
        from companies.models import RecruiterProfile, CompanyAdminProfile
        is_admin = CompanyAdminProfile.objects.filter(user=self.request.user).exists()
        is_recruiter = RecruiterProfile.objects.filter(user=self.request.user).exists()
        if is_recruiter and not is_admin:
            queryset = queryset.filter(job__created_by=self.request.user)
            
        # Filter by job
        job_id = self.request.query_params.get('job_id')
        if job_id:
            queryset = queryset.filter(job_id=job_id)
            
        # Filter by status
        stage = self.request.query_params.get('stage')
        if stage:
            queryset = queryset.filter(current_stage=stage)
            
        return queryset

class ApplicationDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ApplicationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return Application.objects.none()
        company = get_request_company(self.request)
        if not company:
            return Application.objects.none()
        return Application.objects.filter(company=company)

class UpdatePipelineStageView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, pk):
        company = get_request_company(request)
        if not company:
            return Response({"detail": "Unauthorized tenant context."}, status=status.HTTP_401_UNAUTHORIZED)
            
        application = Application.objects.filter(company=company, id=pk).first()
        if not application:
            return Response({"detail": "Application not found."}, status=status.HTTP_404_NOT_FOUND)

        new_stage = request.data.get('stage')
        if not new_stage:
            return Response({"stage": ["This field is required."]}, status=status.HTTP_400_BAD_REQUEST)

        # Ensure stage is in job pipeline stages
        job_stages = application.job.pipeline_stages
        if not isinstance(job_stages, list) or not job_stages:
            job_stages = ["Applied", "Screening", "Coding Round", "Interview", "Offer", "Hired", "Rejected"]
        
        # Match case-insensitively and clean up stage strings
        matched_stage = None
        for stage in job_stages:
            if isinstance(stage, str) and stage.strip().lower() == new_stage.strip().lower():
                matched_stage = stage.strip()
                break

        if not matched_stage:
            return Response({"detail": f"Stage '{new_stage}' is not configured in this job's hiring pipeline."}, status=status.HTTP_400_BAD_REQUEST)

        application.current_stage = matched_stage
        
        # Handle state overrides based on stages
        if matched_stage == 'Offer':
            application.status = 'Offered'
        elif matched_stage == 'Hired':
            application.status = 'Hired'
        elif matched_stage == 'Rejected':
            application.status = 'Rejected'
        else:
            application.status = 'Active'

        application.save()

        # Trigger stage change notification logs / emails
        print(f"[STAGE TRANSITION EMAIL] To: {application.candidate.email} | Subject: Application Update | Body: Your application for {application.job.title} has moved to stage: {new_stage}")

        return Response(ApplicationSerializer(application).data, status=status.HTTP_200_OK)

class AddInternalNoteView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        company = get_request_company(request)
        if not company:
            return Response({"detail": "Unauthorized tenant context."}, status=status.HTTP_401_UNAUTHORIZED)
            
        application = Application.objects.filter(company=company, id=pk).first()
        if not application:
            return Response({"detail": "Application not found."}, status=status.HTTP_404_NOT_FOUND)

        note_text = request.data.get('note')
        if not note_text:
            return Response({"note": ["This field is required."]}, status=status.HTTP_400_BAD_REQUEST)

        # Get recruiter name
        recruiter_name = "System Admin"
        if hasattr(request.user, 'recruiter_profile'):
            recruiter_name = request.user.recruiter_profile.full_name
        elif request.user.first_name:
            recruiter_name = f"{request.user.first_name} {request.user.last_name}".strip()

        new_note = {
            "recruiter": recruiter_name,
            "note": note_text,
            "date": timezone.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        # Initialize internal_notes list if empty
        if not isinstance(application.internal_notes, list):
            application.internal_notes = []

        application.internal_notes.append(new_note)
        application.save()

        return Response(ApplicationSerializer(application).data, status=status.HTTP_200_OK)

class PublicApplyView(views.APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = SubmitApplicationSerializer(data=request.data)
        if serializer.is_valid():
            application = serializer.save()
            return Response({
                "message": "Application submitted successfully.",
                "reference_id": f"APP-{application.id}",
                "application": ApplicationSerializer(application).data
            }, status=status.HTTP_201_CREATED)
            
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class CandidateMyApplicationsView(views.APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        email = request.query_params.get('email')
        if not email:
            return Response({"detail": "email parameter is required."}, status=status.HTTP_400_BAD_REQUEST)
        
        # Get all applications matching the candidate email
        applications = Application.objects.filter(candidate__email=email).order_by('-created_at')
        serializer = ApplicationSerializer(applications, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class CandidateProfileUpdateView(views.APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        email = request.query_params.get('email')
        if not email:
            return Response({"error": "email parameter is required."}, status=status.HTTP_400_BAD_REQUEST)
            
        candidate = Candidate.objects.filter(email=email).first()
        if not candidate:
            return Response({
                "candidate": {
                    "email": email,
                    "first_name": email.split('@')[0].capitalize(),
                    "last_name": "",
                    "phone": "",
                    "parsed_resume": {}
                }
            }, status=status.HTTP_200_OK)
            
        return Response({
            "candidate": {
                "email": candidate.email,
                "first_name": candidate.first_name,
                "last_name": candidate.last_name,
                "phone": candidate.phone,
                "parsed_resume": candidate.parsed_resume
            }
        }, status=status.HTTP_200_OK)

    def patch(self, request):
        email = request.data.get('email')
        if not email:
            return Response({"error": "email is required."}, status=status.HTTP_400_BAD_REQUEST)
            
        parsed_resume = request.data.get('parsed_resume')
        first_name = request.data.get('first_name')
        last_name = request.data.get('last_name')
        phone = request.data.get('phone')
        photo_url = request.data.get('photo_url')

        candidate, created = Candidate.objects.get_or_create(
            email=email,
            defaults={
                'first_name': first_name or email.split('@')[0].capitalize(),
                'last_name': last_name or '',
                'phone': phone or ''
            }
        )
        
        if photo_url is not None:
            if not isinstance(candidate.parsed_resume, dict):
                candidate.parsed_resume = {}
            candidate.parsed_resume['photo_url'] = photo_url
        
        if parsed_resume is not None:
            if not isinstance(candidate.parsed_resume, dict):
                candidate.parsed_resume = {}
            candidate.parsed_resume.update(parsed_resume)
            
            # Check if the user is uploading a new resume document to parse
            documents = parsed_resume.get('documents', []) if isinstance(parsed_resume, dict) else []
            if documents:
                latest_doc = documents[-1]
                doc_url = latest_doc.get('url', '')
                doc_name = latest_doc.get('name', '')
                ext = os.path.splitext(doc_name)[1].lower()
                
                if doc_url and ext in ['.pdf', '.docx', '.doc', '.txt']:
                    try:
                        # Download document
                        res_file = requests.get(doc_url)
                        if res_file.status_code == 200:
                            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                                tmp.write(res_file.content)
                                tmp_path = tmp.name
                            
                            # Parse resume
                            from .parser import parse_resume
                            parsed_data, confidence = parse_resume(tmp_path)
                            os.unlink(tmp_path)
                            
                            if isinstance(parsed_data, dict):
                                # Merge parser results, keeping documents list
                                parsed_data['documents'] = documents
                                candidate.parsed_resume = parsed_data
                                candidate.confidence_score = confidence
                                if parsed_data.get('phone') and not candidate.phone:
                                    candidate.phone = parsed_data['phone']
                                if parsed_data.get('first_name') and not candidate.first_name:
                                    candidate.first_name = parsed_data['first_name']
                                if parsed_data.get('last_name') and not candidate.last_name:
                                    candidate.last_name = parsed_data['last_name']
                    except Exception as e:
                        logger.error(f"Error parsing uploaded document in patch view: {e}")
                        
        if not created:
            if first_name is not None:
                candidate.first_name = first_name
            if last_name is not None:
                candidate.last_name = last_name
            if phone is not None:
                candidate.phone = phone
            
        candidate.save()
        return Response({
            "message": "Candidate profile updated successfully.",
            "candidate": {
                "email": candidate.email,
                "first_name": candidate.first_name,
                "last_name": candidate.last_name,
                "phone": candidate.phone,
                "parsed_resume": candidate.parsed_resume
            }
        }, status=status.HTTP_200_OK)


from .models import CandidateLogin
from datetime import timedelta

class CandidateTrackLoginView(views.APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = request.data.get('email')
        if not email:
            return Response({"error": "email is required."}, status=status.HTTP_400_BAD_REQUEST)

        candidate, created = Candidate.objects.get_or_create(
            email=email,
            defaults={
                'first_name': email.split('@')[0].capitalize(),
                'last_name': '',
                'phone': ''
            }
        )

        today = timezone.localdate()
        CandidateLogin.objects.get_or_create(candidate=candidate, login_date=today)

        logins = CandidateLogin.objects.filter(candidate=candidate).order_by('login_date')
        login_dates = [l.login_date.strftime("%Y-%m-%d") for l in logins]
        login_dates_set = {l.login_date for l in logins}

        # Calculate streak (consecutive days backward from today)
        streak = 0
        current_date = today
        while current_date in login_dates_set:
            streak += 1
            current_date -= timedelta(days=1)

        # If today hasn't been logged yet but yesterday was
        if streak == 0:
            current_date = today - timedelta(days=1)
            while current_date in login_dates_set:
                streak += 1
                current_date -= timedelta(days=1)

        return Response({
            "message": "Login tracked successfully.",
            "streak": streak,
            "login_dates": login_dates
        }, status=status.HTTP_200_OK)


