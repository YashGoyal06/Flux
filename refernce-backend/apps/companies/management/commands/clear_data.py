from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from companies.models import Company, CompanyAdminProfile, RecruiterToken, RecruiterProfile
from jobs.models import Job
from candidates.models import Candidate, Application
from assessments.models import CodingQuestion, CandidateAssessment
from interviews.models import InterviewSession

class Command(BaseCommand):
    help = 'Clears all data from the HireSync Pro database tables'

    def handle(self, *args, **kwargs):
        self.stdout.write('Clearing all database records...')

        # Delete all records (cascading deletes will clear profiles, applications, etc.)
        InterviewSession.objects.all().delete()
        CandidateAssessment.objects.all().delete()
        CodingQuestion.objects.all().delete()
        Application.objects.all().delete()
        Candidate.objects.all().delete()
        Job.objects.all().delete()
        RecruiterToken.objects.all().delete()
        RecruiterProfile.objects.all().delete()
        CompanyAdminProfile.objects.all().delete()
        Company.objects.all().delete()
        
        # Clear users (except superusers if they want to keep them, or delete everything)
        # Let's delete all users to make it 100% clean
        User.objects.all().delete()

        self.stdout.write('Database cleared successfully!')
