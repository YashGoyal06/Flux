from django.core.management.base import BaseCommand
from django.contrib.auth.models import User

from companies.models import Company, CompanyAdminProfile, RecruiterToken, RecruiterProfile
from assessments.models import CodingQuestion, CandidateAssessment
from jobs.models import Job
from candidates.models import Candidate, Application
from interviews.models import InterviewSession
from authentication.models import TestCredential


class Command(BaseCommand):
    help = 'Flushes ALL seeded mock/demo data from the Supabase database'

    def handle(self, *args, **kwargs):
        self.stdout.write('\n' + '='*60)
        self.stdout.write(' 🗑️  FLUSHING ALL MOCK DATA FROM SUPABASE DATABASE')
        self.stdout.write('='*60 + '\n')

        # 1. Delete Test Credentials
        count = TestCredential.objects.all().delete()[0]
        self.stdout.write(f'  ✅ Deleted {count} TestCredential(s)')

        # 2. Delete Interview Sessions
        count = InterviewSession.objects.all().delete()[0]
        self.stdout.write(f'  ✅ Deleted {count} InterviewSession(s)')

        # 3. Delete Candidate Assessments
        count = CandidateAssessment.objects.all().delete()[0]
        self.stdout.write(f'  ✅ Deleted {count} CandidateAssessment(s)')

        # 4. Delete Applications
        count = Application.objects.all().delete()[0]
        self.stdout.write(f'  ✅ Deleted {count} Application(s)')

        # 5. Delete Candidates
        count = Candidate.objects.all().delete()[0]
        self.stdout.write(f'  ✅ Deleted {count} Candidate(s)')

        # 6. Delete Coding Questions
        count = CodingQuestion.objects.all().delete()[0]
        self.stdout.write(f'  ✅ Deleted {count} CodingQuestion(s)')

        # 7. Delete Jobs
        count = Job.objects.all().delete()[0]
        self.stdout.write(f'  ✅ Deleted {count} Job(s)')

        # 8. Delete Recruiter Profiles
        count = RecruiterProfile.objects.all().delete()[0]
        self.stdout.write(f'  ✅ Deleted {count} RecruiterProfile(s)')

        # 9. Delete Recruiter Tokens
        count = RecruiterToken.objects.all().delete()[0]
        self.stdout.write(f'  ✅ Deleted {count} RecruiterToken(s)')

        # 10. Delete Company Admin Profiles
        count = CompanyAdminProfile.objects.all().delete()[0]
        self.stdout.write(f'  ✅ Deleted {count} CompanyAdminProfile(s)')

        # 11. Delete Companies
        count = Company.objects.all().delete()[0]
        self.stdout.write(f'  ✅ Deleted {count} Company(s)')

        # 12. Delete all non-superuser Django Users created by seeding
        count = User.objects.all().delete()[0]
        self.stdout.write(f'  ✅ Deleted {count} User(s)')

        self.stdout.write('\n' + '='*60)
        self.stdout.write(' ✅ ALL MOCK DATA HAS BEEN FLUSHED FROM SUPABASE!')
        self.stdout.write('='*60 + '\n')
