from django.db import models
from django.utils import timezone
from companies.models import TenantModel
from candidates.models import Candidate
from jobs.models import Job
import uuid

class InterviewSession(TenantModel):
    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE, related_name="interviews")
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="interviews")
    room_id = models.CharField(max_length=100, default=uuid.uuid4, unique=True)
    scheduled_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(null=True, blank=True)
    recording_url = models.URLField(max_length=1000, null=True, blank=True)
    
    # Recruiter notes, only accessible to the company recruiters
    private_notes = models.TextField(blank=True, null=True)
    
    # Structured scorecard feedback:
    # {"technical_skills": 4, "communication": 3, "problem_solving": 4, "culture_fit": 5, "recommendation": "Yes", "notes": "..."}
    feedback = models.JSONField(default=dict, blank=True)
    questions = models.JSONField(default=list, blank=True) # Isolated list of coding questions for this specific interview room
    created_at = models.DateTimeField(default=timezone.now)


    def __str__(self):
        return f"Interview with {self.candidate.email} for {self.job.title}"
