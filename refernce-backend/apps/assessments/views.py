from rest_framework import views, status, permissions, generics
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from .models import CandidateAssessment, CodingQuestion
from .serializers import CandidateAssessmentSerializer, RunCodeSerializer, SubmitCodeSerializer, CodingQuestionSerializer, ExecuteCodeSerializer
from .runner import run_code
from django.utils import timezone
from datetime import timedelta
from candidates.models import Candidate
from jobs.models import Job


def get_gradable_test_cases(test_cases):
    if not isinstance(test_cases, list):
        return []

    usable_cases = [
        case for case in test_cases
        if isinstance(case, dict) and str(case.get('expected_output', '')).strip()
    ]

    # PDF/Codeforces imports currently use this single placeholder when no real
    # sample output was available. Treat it as manual review instead of grading.
    if len(usable_cases) == 1:
        only_case = usable_cases[0]
        if str(only_case.get('input', '')).strip() == '1' and str(only_case.get('expected_output', '')).strip() == '1':
            return []

    return usable_cases

class CodingQuestionsListView(generics.ListAPIView):
    """Return coding questions. Authenticated users get company + public questions."""
    serializer_class = CodingQuestionSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        from django.db.models import Q
        company = getattr(self.request, 'company', None)
        if company:
            return CodingQuestion.objects.filter(Q(company=company) | Q(company__isnull=True)).order_by('difficulty', 'id')
        return CodingQuestion.objects.filter(company__isnull=True).order_by('difficulty', 'id')



class AssignAssessmentView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        # Resolve company context robustly
        company = getattr(request, 'company', None)
        if not company and request.user.is_authenticated:
            from companies.models import CompanyAdminProfile, RecruiterProfile
            admin_profile = CompanyAdminProfile.objects.filter(user=request.user).first()
            if admin_profile:
                company = admin_profile.company
            else:
                recruiter_profile = RecruiterProfile.objects.filter(user=request.user).first()
                if recruiter_profile:
                    company = recruiter_profile.company

        if not company:
            return Response({"detail": "Unauthorized tenant context."}, status=status.HTTP_401_UNAUTHORIZED)
        candidate_id = request.data.get('candidate_id')
        job_id = request.data.get('job_id')
        question_ids = request.data.get('question_ids', [])
        duration_minutes = request.data.get('duration_minutes', 60)

        if not candidate_id or not job_id:
            return Response({"detail": "candidate_id and job_id are required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            candidate = Candidate.objects.get(id=candidate_id)
            job = Job.objects.get(id=job_id, company=company)
        except (Candidate.DoesNotExist, Job.DoesNotExist):
            return Response({"detail": "Candidate or Job not found in this company."}, status=status.HTTP_404_NOT_FOUND)

        # Create assessment
        expires_at = timezone.now() + timedelta(days=7) # Expires in 7 days by default
        assessment = CandidateAssessment.objects.create(
            company=company,
            candidate=candidate,
            job=job,
            expires_at=expires_at,
            duration_minutes=duration_minutes
        )

        # Set questions
        if question_ids:
            questions = CodingQuestion.objects.filter(id__in=question_ids)
            assessment.questions.set(questions)
        else:
            # Assign standard questions
            default_questions = CodingQuestion.objects.filter(company__isnull=True)[:2]
            assessment.questions.set(default_questions)

        assessment.save()

        # Send invite email mock
        print(f"[ASSESSMENT INVITE EMAIL] To: {candidate.email} | Subject: Coding Assessment Invitation | Room Token: {assessment.token}")

        return Response(CandidateAssessmentSerializer(assessment).data, status=status.HTTP_201_CREATED)

class CandidateAssessmentSessionView(views.APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, token):
        try:
            assessment = CandidateAssessment.objects.get(token=token)
        except CandidateAssessment.DoesNotExist:
            return Response({"detail": "Invalid assessment token."}, status=status.HTTP_404_NOT_FOUND)

        if assessment.is_expired():
            return Response({"detail": "This coding assessment link has expired."}, status=status.HTTP_400_BAD_REQUEST)

        if assessment.completed_at:
            return Response({
                "detail": "This assessment has already been completed.",
                "completed": True
            }, status=status.HTTP_200_OK)

        # Start the timer on first access
        if not assessment.started_at:
            assessment.started_at = timezone.now()
            assessment.save()

        # Validate time limit
        if not assessment.has_time_remaining():
            assessment.completed_at = timezone.now()
            assessment.save()
            return Response({
                "detail": "Time has run out for this assessment.",
                "completed": True
            }, status=status.HTTP_200_OK)

        return Response(CandidateAssessmentSerializer(assessment).data, status=status.HTTP_200_OK)

class RunCodeView(views.APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, token):
        try:
            assessment = CandidateAssessment.objects.get(token=token)
        except CandidateAssessment.DoesNotExist:
            return Response({"detail": "Invalid session token."}, status=status.HTTP_404_NOT_FOUND)

        if assessment.completed_at or not assessment.has_time_remaining():
            return Response({"detail": "Assessment session is closed."}, status=status.HTTP_400_BAD_REQUEST)

        serializer = RunCodeSerializer(data=request.data)
        if serializer.is_valid():
            q_id = serializer.validated_data['question_id']
            code = serializer.validated_data['code']
            language = serializer.validated_data['language']
            stdin = serializer.validated_data.get('stdin', '')
            expected_output = serializer.validated_data.get('expected_output', '')

            try:
                question = assessment.questions.get(id=q_id)
            except CodingQuestion.DoesNotExist:
                return Response({"detail": "Question not in assessment."}, status=status.HTTP_404_NOT_FOUND)

            # Run code using runner
            run_result = run_code(code, language, stdin, expected_output)
            return Response(run_result, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ExecuteCodeView(views.APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = ExecuteCodeSerializer(data=request.data)
        if serializer.is_valid():
            result = run_code(
                serializer.validated_data['code'],
                serializer.validated_data['language'],
                serializer.validated_data.get('stdin', ''),
                serializer.validated_data.get('expected_output', '')
            )
            return Response(result, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class SubmitSolutionView(views.APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, token):
        try:
            assessment = CandidateAssessment.objects.get(token=token)
        except CandidateAssessment.DoesNotExist:
            return Response({"detail": "Invalid session token."}, status=status.HTTP_404_NOT_FOUND)

        if assessment.completed_at or not assessment.has_time_remaining():
            return Response({"detail": "Assessment session is closed."}, status=status.HTTP_400_BAD_REQUEST)

        serializer = SubmitCodeSerializer(data=request.data)
        if serializer.is_valid():
            q_id = serializer.validated_data['question_id']
            code = serializer.validated_data['code']
            language = serializer.validated_data['language']

            try:
                question = assessment.questions.get(id=q_id)
            except CodingQuestion.DoesNotExist:
                return Response({"detail": "Question not in assessment."}, status=status.HTTP_404_NOT_FOUND)

            # Store the submission code
            if not isinstance(assessment.submissions, dict):
                assessment.submissions = {}
            assessment.submissions[str(q_id)] = {
                "code": code,
                "language": language,
                "submitted_at": timezone.now().strftime("%Y-%m-%d %H:%M:%S")
            }

            # Grade only when the question has real expected outputs.
            test_cases = get_gradable_test_cases(question.test_cases)
            passed_cases = 0
            total_cases = len(test_cases)
            details = []

            if total_cases == 0:
                if not isinstance(assessment.results, dict):
                    assessment.results = {}
                assessment.results[str(q_id)] = {
                    "passed_cases": 0,
                    "total_cases": 0,
                    "status": "Manual Review",
                    "details": [],
                    "requires_manual_review": True
                }
                assessment.save()

                return Response({
                    "message": "Question submitted for recruiter review.",
                    "passed_cases": 0,
                    "total_cases": 0,
                    "status": "Manual Review",
                    "details": [],
                    "requires_manual_review": True
                }, status=status.HTTP_200_OK)

            for case in test_cases:
                inp = case.get('input', '')
                expected = case.get('expected_output', '')
                is_hidden = case.get('is_hidden', False)

                result = run_code(code, language, inp, expected)
                if result.get('success'):
                    passed_cases += 1
                
                details.append({
                    "success": result.get('success'),
                    "status": result.get('status'),
                    "stdout": result.get('stdout') if not is_hidden else "[HIDDEN]",
                    "stderr": result.get('stderr'),
                    "is_hidden": is_hidden
                })

            status_str = "Passed" if passed_cases == total_cases else "Failed"

            # Store the grades
            if not isinstance(assessment.results, dict):
                assessment.results = {}
            assessment.results[str(q_id)] = {
                "passed_cases": passed_cases,
                "total_cases": total_cases,
                "status": status_str,
                "details": details,
                "requires_manual_review": False
            }

            assessment.save()

            return Response({
                "message": "Question submitted successfully.",
                "passed_cases": passed_cases,
                "total_cases": total_cases,
                "status": status_str,
                "details": details
            }, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class FinishAssessmentView(views.APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, token):
        try:
            assessment = CandidateAssessment.objects.get(token=token)
        except CandidateAssessment.DoesNotExist:
            return Response({"detail": "Invalid session token."}, status=status.HTTP_404_NOT_FOUND)

        assessment.completed_at = timezone.now()
        assessment.save()

        # Update candidate pipeline state to coding complete
        # We can update the candidate's application linked to this job
        from candidates.models import Application
        application = Application.objects.filter(job=assessment.job, candidate=assessment.candidate).first()
        if application:
            application.current_stage = "Interview"  # advance them or flag complete
            application.save()

        return Response({
            "message": "Assessment marked as completed successfully.",
            "completed_at": assessment.completed_at
        }, status=status.HTTP_200_OK)
