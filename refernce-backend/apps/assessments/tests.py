from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status
from datetime import timedelta
from companies.models import Company, CompanyAdminProfile
from jobs.models import Job
from candidates.models import Candidate, Application
from assessments.models import CodingQuestion, CandidateAssessment

class AssessmentTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Create Company
        self.company = Company.objects.create(name="Talvex Inc", domain="talvex.com")
        self.user = User.objects.create_user(username="recruiter", email="recruiter@talvex.com", password="password123")
        self.profile = CompanyAdminProfile.objects.create(user=self.user, company=self.company)

        # Create Job
        self.job = Job.objects.create(
            company=self.company,
            title="Senior Dev",
            department="Eng",
            location="Remote",
            pipeline_stages=["Applied", "Coding Round", "Interview", "Offer"]
        )

        # Create Candidate
        self.candidate = Candidate.objects.create(
            first_name="David",
            last_name="Chen",
            email="david.chen@example.com"
        )

        # Create Application
        self.app = Application.objects.create(
            company=self.company,
            job=self.job,
            candidate=self.candidate,
            current_stage="Applied"
        )

        # Create Coding Question
        self.question = CodingQuestion.objects.create(
            title="Two Sum",
            description="Find two numbers that add up to target.",
            difficulty="Easy",
            test_cases=[
                {"input": "2,7,11,15\n9", "expected_output": "0,1", "is_hidden": False}
            ]
        )

    def test_assign_assessment(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            '/api/assessments/assign/',
            data={
                "candidate_id": self.candidate.id,
                "job_id": self.job.id,
                "question_ids": [self.question.id],
                "duration_minutes": 45
            },
            format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("token", response.data)
        
        assessment = CandidateAssessment.objects.get(token=response.data["token"])
        self.assertEqual(assessment.duration_minutes, 45)
        self.assertIn(self.question, assessment.questions.all())

    def test_get_assessment_session(self):
        assessment = CandidateAssessment.objects.create(
            company=self.company,
            candidate=self.candidate,
            job=self.job,
            duration_minutes=60,
            expires_at=timezone.now() + timedelta(days=2)
        )
        assessment.questions.add(self.question)

        # Access via token without authentication
        response = self.client.get(f'/api/assessments/session/{assessment.token}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("questions", response.data)
        
        # Verify timer started
        assessment.refresh_from_db()
        self.assertIsNotNone(assessment.started_at)

    def test_submit_solution_and_finish_pipeline(self):
        assessment = CandidateAssessment.objects.create(
            company=self.company,
            candidate=self.candidate,
            job=self.job,
            duration_minutes=60,
            expires_at=timezone.now() + timedelta(days=2),
            started_at=timezone.now()
        )
        assessment.questions.add(self.question)

        # Mock submit code (simulating grading passes)
        # Note: Code execution runner is mocked or bypassed in standard test configurations,
        # but let's test the endpoint schema handles it.
        response = self.client.post(
            f'/api/assessments/session/{assessment.token}/submit/',
            data={
                "question_id": self.question.id,
                "code": "def two_sum(nums, target): return [0, 1]",
                "language": "python"
            },
            format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Finish assessment
        response_finish = self.client.post(f'/api/assessments/session/{assessment.token}/finish/')
        self.assertEqual(response_finish.status_code, status.HTTP_200_OK)

        # Verify application advanced
        self.app.refresh_from_db()
        self.assertEqual(self.app.current_stage, "Interview")
