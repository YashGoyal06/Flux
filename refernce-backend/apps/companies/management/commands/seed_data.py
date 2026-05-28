from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
import hashlib

from companies.models import Company, CompanyAdminProfile, RecruiterToken, RecruiterProfile
from assessments.models import CodingQuestion
from jobs.models import Job
from candidates.models import Candidate, Application
from interviews.models import InterviewSession
from authentication.models import TestCredential

class Command(BaseCommand):
    help = 'Seeds default test data for HireSync Pro'

    def handle(self, *args, **kwargs):
        self.stdout.write('Seeding test data...')

        # 1. Create Default Company
        company, created = Company.objects.get_or_create(
            domain='talvex.com',
            defaults={
                'name': 'Talvex Corp',
                'description': 'A modern tech platform',
                'industry': 'Technology',
                'size': '50-200'
            }
        )
        if created:
            self.stdout.write(f'Created Company: {company.name}')
        else:
            self.stdout.write(f'Company {company.name} already exists.')

        # 2. Create Default Company Admin User
        admin_email = 'admin@talvex.com'
        admin_username = 'admin_demo'
        if not User.objects.filter(username=admin_username).exists():
            admin_user = User.objects.create_superuser(
                username=admin_username,
                email=admin_email,
                password='demo1234'
            )
            admin_user.first_name = 'Rohan'
            admin_user.last_name = 'Mehta'
            admin_user.save()
            
            CompanyAdminProfile.objects.create(
                user=admin_user,
                company=company,
                is_2fa_enabled=False
            )
            self.stdout.write('Created Superuser admin_demo / password: demo1234')
        else:
            self.stdout.write('Superuser admin_demo already exists.')

        # 3. Create Recruiter Invitation Token & Profile
        recruiter_email = 'recruiter@talvex.com'
        raw_token = 'demo_recruiter_token_64_characters_long_for_testing_purposes_123'
        token_hash = hashlib.sha256(raw_token.encode('utf-8')).hexdigest()
        expires_at = timezone.now() + timedelta(days=30)

        token_obj, token_created = RecruiterToken.objects.get_or_create(
            email=recruiter_email,
            company=company,
            defaults={
                'token_hash': token_hash,
                'is_used': True,  # Mark as used so Sarah can log in directly
                'is_revoked': False,
                'expires_at': expires_at
            }
        )
        if token_created:
            self.stdout.write(f'Created Recruiter Invite Token:\nEmail: {recruiter_email}\nRaw Token: {raw_token}')
        else:
            token_obj.token_hash = token_hash
            token_obj.is_used = True
            token_obj.save()
            self.stdout.write(f'Recruiter Invite Token for {recruiter_email} verified and updated.')

        recruiter_username = 'recruiter_demo'
        recruiter_user = User.objects.filter(username=recruiter_username).first()
        if not recruiter_user:
            recruiter_user = User.objects.create_user(
                username=recruiter_username,
                email=recruiter_email,
                password=None
            )
            recruiter_user.first_name = 'Sarah'
            recruiter_user.last_name = 'Jenkins'
            recruiter_user.save()

            RecruiterProfile.objects.get_or_create(
                company=company,
                user=recruiter_user,
                defaults={
                    'full_name': 'Sarah Jenkins',
                    'job_title': 'Lead Recruiter',
                    'department': 'Talent Acquisition',
                    'phone_number': '+1 (555) 019-2834',
                    'specialization_areas': ['Product', 'Engineering', 'Design'],
                    'years_of_experience': '5-8 years',
                    'bio': 'Lead recruiter at Talvex Corp helping build world-class engineering teams.',
                    'preferred_timezone': 'UTC',
                    'photo_url': 'https://i.pravatar.cc/150?u=sarah_jenkins'
                }
            )
            self.stdout.write('Created Recruiter user and profile for Sarah Jenkins.')
        else:
            self.stdout.write('Recruiter user recruiter_demo already exists.')

        # 4. Create Public Coding Questions
        questions_data = [
            {
                "title": "Two Sum",
                "difficulty": "Easy",
                "description": "Given an array of integers nums and an integer target, return indices of the two numbers such that they add up to target.",
                "starter_code": {
                    "javascript": "function twoSum(nums, target) {\n  // Your solution here\n  \n}",
                    "python": "def twoSum(nums, target):\n    # Your solution here\n    pass"
                },
                "test_cases": [
                    {"input": "[2, 7, 11, 15]\n9", "expected_output": "[0, 1]", "is_hidden": False},
                    {"input": "[3, 2, 4]\n6", "expected_output": "[1, 2]", "is_hidden": False}
                ]
            },
            {
                "title": "Valid Parentheses",
                "difficulty": "Easy",
                "description": "Given a string s containing just the characters '(', ')', '{', '}', '[' and ']', determine if the input string is valid.",
                "starter_code": {
                    "javascript": "function isValid(s) {\n  // Your solution here\n  \n}",
                    "python": "def isValid(s):\n    # Your solution here\n    pass"
                },
                "test_cases": [
                    {"input": "\"()\"", "expected_output": "true", "is_hidden": False},
                    {"input": "\"()[]{}\"", "expected_output": "true", "is_hidden": False},
                    {"input": "\"(]\"", "expected_output": "false", "is_hidden": False}
                ]
            }
        ]

        for q in questions_data:
            q_obj, q_created = CodingQuestion.objects.get_or_create(
                title=q["title"],
                company=None, # Public question
                defaults={
                    "difficulty": q["difficulty"],
                    "description": q["description"],
                    "starter_code": q["starter_code"],
                    "test_cases": q["test_cases"]
                }
            )
            if q_created:
                self.stdout.write(f'Created Coding Question: {q["title"]}')
            else:
                self.stdout.write(f'Coding Question {q["title"]} already exists.')

        # 5. Create Jobs (Requisitions)
        job_data = [
            {
                "title": "Senior Frontend Engineer",
                "department": "Engineering",
                "location": "Remote",
                "type": "Full-time",
                "priority": "Urgent",
                "status": "Active",
                "description": "We are seeking a Senior Frontend Engineer with deep expertise in React and modern UI/UX design. You will be building responsive interfaces and guiding the architecture of our user-facing products.",
                "requirements": ["5+ years of experience with React/TypeScript", "Strong understanding of browser rendering and performance optimization", "Experience with Tailwind CSS and modern styling solutions"]
            },
            {
                "title": "Product Designer",
                "department": "Design",
                "location": "New York, NY",
                "type": "Full-time",
                "priority": "Normal",
                "status": "Active",
                "description": "We are looking for a Product Designer to own user research, prototyping, and final high-fidelity designs for our core workflow products. You will collaborate closely with product management and engineering.",
                "requirements": ["3+ years of product design experience", "Mastery of Figma and prototyping tools", "Strong portfolio showcasing user-centric design methodologies"]
            },
            {
                "title": "Data Scientist",
                "department": "Data",
                "location": "Remote",
                "type": "Contract",
                "priority": "Normal",
                "status": "Active",
                "description": "We are hiring a contract Data Scientist to build predictive analytics features and optimize our recommendation engines. Strong knowledge of machine learning and database querying is required.",
                "requirements": ["Proficiency in Python, SQL, and pandas/numpy", "Experience building and deploying machine learning models in production", "Excellent statistical analysis skills"]
            }
        ]

        jobs_list = []
        for jd in job_data:
            job, created = Job.objects.get_or_create(
                title=jd["title"],
                company=company,
                defaults={
                    "department": jd["department"],
                    "location": jd["location"],
                    "type": jd["type"],
                    "priority": jd["priority"],
                    "status": jd["status"],
                    "description": jd["description"],
                    "requirements": jd["requirements"],
                    "pipeline_stages": ["Applied", "Screening", "Coding Round", "Interview", "Offer", "Hired", "Rejected"]
                }
            )
            jobs_list.append(job)
            if created:
                self.stdout.write(f'Created Job: {job.title}')
            else:
                self.stdout.write(f'Job {job.title} already exists.')

        # 6. Create Candidates & Applications
        candidate_data = [
            {
                "first_name": "Elena",
                "last_name": "Rostova",
                "email": "elena.rostova@example.com",
                "phone": "+1 (555) 234-5678",
                "parsed_resume": {
                    "skills": ["React", "TypeScript", "System Design", "JavaScript", "HTML", "CSS"],
                    "photo_url": "https://i.pravatar.cc/150?u=elena_rostova"
                },
                "confidence_score": 0.92,
                "stage": "Applied",
                "job": jobs_list[0]
            },
            {
                "first_name": "Marcus",
                "last_name": "Sterling",
                "email": "marcus.sterling@example.com",
                "phone": "+1 (555) 876-5432",
                "parsed_resume": {
                    "skills": ["Figma", "Prototyping", "User Research", "Wireframing", "UI Design"],
                    "photo_url": "https://i.pravatar.cc/150?u=marcus_sterling"
                },
                "confidence_score": 0.88,
                "stage": "Screening",
                "job": jobs_list[1]
            },
            {
                "first_name": "David",
                "last_name": "Chen",
                "email": "david.chen@example.com",
                "phone": "+1 (555) 345-6789",
                "parsed_resume": {
                    "skills": ["React", "Vite", "Tailwind CSS", "JavaScript", "Redux"],
                    "photo_url": "https://i.pravatar.cc/150?u=david_chen"
                },
                "confidence_score": 0.95,
                "stage": "Coding Round",
                "job": jobs_list[0]
            },
            {
                "first_name": "Aisha",
                "last_name": "Patel",
                "email": "aisha.patel@example.com",
                "phone": "+1 (555) 765-4321",
                "parsed_resume": {
                    "skills": ["Node.js", "PostgreSQL", "AWS", "Python", "Docker"],
                    "photo_url": "https://i.pravatar.cc/150?u=aisha_patel"
                },
                "confidence_score": 0.98,
                "stage": "Interview",
                "job": jobs_list[0]
            },
            {
                "first_name": "James",
                "last_name": "Wilson",
                "email": "james.wilson@example.com",
                "phone": "+1 (555) 456-7890",
                "parsed_resume": {
                    "skills": ["Python", "Machine Learning", "SQL", "Pandas", "PyTorch"],
                    "photo_url": "https://i.pravatar.cc/150?u=james_wilson"
                },
                "confidence_score": 0.89,
                "stage": "Offer",
                "job": jobs_list[2]
            }
        ]

        candidates_list = []
        for cd in candidate_data:
            candidate, created = Candidate.objects.get_or_create(
                email=cd["email"],
                defaults={
                    "first_name": cd["first_name"],
                    "last_name": cd["last_name"],
                    "phone": cd["phone"],
                    "parsed_resume": cd["parsed_resume"],
                    "confidence_score": cd["confidence_score"]
                }
            )
            candidates_list.append(candidate)
            if created:
                self.stdout.write(f'Created Candidate: {candidate.first_name} {candidate.last_name}')

            # Create application
            app, app_created = Application.objects.get_or_create(
                job=cd["job"],
                candidate=candidate,
                company=company,
                defaults={
                    "current_stage": cd["stage"],
                    "resume_file": "resumes/placeholder.pdf",
                    "status": "Active"
                }
            )
            if app_created:
                self.stdout.write(f'Created Application for {candidate.first_name} to {cd["job"].title}')

        # 6b. Create Demo Candidate (for candidate@demo.com login)
        demo_candidate, demo_created = Candidate.objects.get_or_create(
            email='candidate@demo.com',
            defaults={
                'first_name': 'Demo',
                'last_name': 'Candidate',
                'phone': '+1 (555) 000-0001',
                'parsed_resume': {
                    'skills': ['JavaScript', 'React', 'Node.js', 'Python'],
                    'photo_url': 'https://i.pravatar.cc/150?u=demo_candidate'
                },
                'confidence_score': 0.78
            }
        )
        if demo_created:
            self.stdout.write('Created Demo Candidate: candidate@demo.com')

        demo_app, demo_app_created = Application.objects.get_or_create(
            job=jobs_list[0],
            candidate=demo_candidate,
            company=company,
            defaults={
                'current_stage': 'Interview',
                'resume_file': 'resumes/placeholder.pdf',
                'status': 'Active'
            }
        )
        if demo_app_created:
            self.stdout.write(f'Created Application for demo candidate -> {jobs_list[0].title}')

        demo_session, demo_sess_created = InterviewSession.objects.get_or_create(
            room_id='DEMO-ROOM-001',
            company=company,
            defaults={
                'candidate': demo_candidate,
                'job': jobs_list[0],
                'scheduled_at': timezone.now() + timedelta(hours=1),
                'completed_at': None,
                'feedback': {}
            }
        )
        if demo_sess_created:
            self.stdout.write(f'Created Demo Interview Session: DEMO-ROOM-001')

        # 7. Create Live Interview Sessions
        interview_data = [
            {
                "candidate": candidates_list[2], # David Chen
                "job": jobs_list[0],
                "room_id": "INT-9921",
                "scheduled_at": timezone.now() - timedelta(hours=2),
                "completed_at": timezone.now() - timedelta(hours=1),
                "feedback": {"technical_skills": 4, "communication": 4, "problem_solving": 4, "culture_fit": 4, "recommendation": "Yes", "notes": "Solid technical capability, structured code style."}
            },
            {
                "candidate": candidates_list[3], # Aisha Patel
                "job": jobs_list[0],
                "room_id": "INT-9922",
                "scheduled_at": timezone.now() + timedelta(hours=2),
                "completed_at": None,
                "feedback": {}
            },
            {
                "candidate": candidates_list[4], # James Wilson
                "job": jobs_list[2],
                "room_id": "INT-9923",
                "scheduled_at": timezone.now() + timedelta(hours=4),
                "completed_at": None,
                "feedback": {}
            }
        ]

        for idt in interview_data:
            session, created = InterviewSession.objects.get_or_create(
                room_id=idt["room_id"],
                company=company,
                defaults={
                    "candidate": idt["candidate"],
                    "job": idt["job"],
                    "scheduled_at": idt["scheduled_at"],
                    "completed_at": idt["completed_at"],
                    "feedback": idt["feedback"]
                }
            )
            if created:
                self.stdout.write(f'Created Interview Session room: {session.room_id}')
            else:
                self.stdout.write(f'Interview Session room {session.room_id} already exists.')

        # 8. Create Test Credentials for frontend query
        test_creds_data = [
            {
                "role": "admin",
                "label": "Enterprise Admin",
                "email": "admin@talvex.com",
                "password": "demo1234"
            },
            {
                "role": "recruiter",
                "label": "Recruiter Lead",
                "email": "recruiter@talvex.com",
                "password": "demo_recruiter_token_64_characters_long_for_testing_purposes_123"
            },
            {
                "role": "candidate",
                "label": "Standard Candidate",
                "email": "candidate@demo.com",
                "password": "demo1234"
            },
            {
                "role": "candidate",
                "label": "Candidate (Elena)",
                "email": "elena.rostova@example.com",
                "password": "demo1234"
            }
        ]

        for tc in test_creds_data:
            tc_obj, tc_created = TestCredential.objects.get_or_create(
                role=tc["role"],
                email=tc["email"],
                defaults={
                    "label": tc["label"],
                    "password": tc["password"]
                }
            )
            if tc_created:
                self.stdout.write(f'Created Test Credential for role {tc["role"]}: {tc["email"]}')
            else:
                tc_obj.label = tc["label"]
                tc_obj.password = tc["password"]
                tc_obj.save()
                self.stdout.write(f'Updated Test Credential for role {tc["role"]}: {tc["email"]}')

        self.stdout.write('Seeding completed successfully!')
