from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework import status
from companies.models import Company, CompanyAdminProfile, RecruiterProfile
from jobs.models import Job
from candidates.models import Candidate, Application

class PipelineMultiTenancyTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Create Company A
        self.company_a = Company.objects.create(name="Company A", domain="comp-a.com")
        self.user_a = User.objects.create_user(username="admin_a", email="admin@comp-a.com", password="password123")
        self.admin_profile_a = CompanyAdminProfile.objects.create(user=self.user_a, company=self.company_a)

        # Create Company B
        self.company_b = Company.objects.create(name="Company B", domain="comp-b.com")
        self.user_b = User.objects.create_user(username="admin_b", email="admin@comp-b.com", password="password123")
        self.admin_profile_b = CompanyAdminProfile.objects.create(user=self.user_b, company=self.company_b)

        # Create Jobs
        self.job_a = Job.objects.create(
            company=self.company_a,
            title="Frontend Dev",
            department="Eng",
            location="Remote",
            pipeline_stages=["Applied", "Screening", "Interview", "Offer"]
        )
        self.job_b = Job.objects.create(
            company=self.company_b,
            title="Backend Dev",
            department="Eng",
            location="Remote",
            pipeline_stages=["Applied", "Interview", "Hired"]
        )

        # Create Candidate
        self.candidate = Candidate.objects.create(
            first_name="Elena",
            last_name="Rostova",
            email="elena@rostova.com",
            confidence_score=0.92
        )

        # Create Applications
        self.app_a = Application.objects.create(
            company=self.company_a,
            job=self.job_a,
            candidate=self.candidate,
            current_stage="Applied",
            status="Active"
        )
        self.app_b = Application.objects.create(
            company=self.company_b,
            job=self.job_b,
            candidate=self.candidate,
            current_stage="Applied",
            status="Active"
        )

    def test_recruiter_pipeline_access_is_tenant_scoped(self):
        # Authenticate as Company A Admin
        self.client.force_authenticate(user=self.user_a)

        # Fetch pipeline - should only return Application A
        response = self.client.get('/api/candidates/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['id'], self.app_a.id)

        # Try to view Application B - should return 404
        response_detail = self.client.get(f'/api/candidates/{self.app_b.id}/')
        self.assertEqual(response_detail.status_code, status.HTTP_404_NOT_FOUND)

    def test_stage_transition_valid(self):
        # Authenticate as Company A Admin
        self.client.force_authenticate(user=self.user_a)

        # Change Application A stage to Interview (which is configured in job_a)
        response = self.client.patch(
            f'/api/candidates/{self.app_a.id}/stage/',
            data={"stage": "Interview"},
            format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.app_a.refresh_from_db()
        self.assertEqual(self.app_a.current_stage, "Interview")
        self.assertEqual(self.app_a.status, "Active")

    def test_stage_transition_invalid_for_job(self):
        # Authenticate as Company A Admin
        self.client.force_authenticate(user=self.user_a)

        # Try to change to a stage not in pipeline stages (e.g. Hired)
        response = self.client.patch(
            f'/api/candidates/{self.app_a.id}/stage/',
            data={"stage": "Hired"},
            format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("not configured in this job's hiring pipeline", response.data['detail'])

    def test_stage_transition_cross_tenant_blocked(self):
        # Authenticate as Company A Admin
        self.client.force_authenticate(user=self.user_a)

        # Try to update stage of Application B (Company B)
        response = self.client.patch(
            f'/api/candidates/{self.app_b.id}/stage/',
            data={"stage": "Interview"},
            format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_add_internal_note_tenant_scoped(self):
        # Authenticate as Company A Admin
        self.client.force_authenticate(user=self.user_a)

        # Add note to App A
        response = self.client.post(
            f'/api/candidates/{self.app_a.id}/notes/',
            data={"note": "Excellent technical interview."},
            format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.app_a.refresh_from_db()
        self.assertEqual(len(self.app_a.internal_notes), 1)
        self.assertEqual(self.app_a.internal_notes[0]['note'], "Excellent technical interview.")

        # Try to add note to App B - should 404
        response_b = self.client.post(
            f'/api/candidates/{self.app_b.id}/notes/',
            data={"note": "Should fail."},
            format="json"
        )
        self.assertEqual(response_b.status_code, status.HTTP_404_NOT_FOUND)
