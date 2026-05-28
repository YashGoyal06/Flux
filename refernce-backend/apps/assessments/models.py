from django.db import models
from django.utils import timezone
from companies.models import TenantModel
from candidates.models import Candidate
from jobs.models import Job
import uuid

class CodingQuestion(models.Model):
    # Company can be null for standard platform-provided questions
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, null=True, blank=True, related_name="coding_questions")
    title = models.CharField(max_length=255)
    difficulty = models.CharField(max_length=50, default="Easy") # Easy, Medium, Hard
    description = models.TextField()
    starter_code = models.JSONField(default=dict) # {"javascript": "...", "python": "..."}
    test_cases = models.JSONField(default=list) # [{"input": "...", "expected_output": "...", "is_hidden": false}]
    time_limit = models.IntegerField(default=5) # seconds
    memory_limit = models.IntegerField(default=128000) # KB
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.title

class CandidateAssessment(TenantModel):
    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE, related_name="assessments")
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="assessments")
    questions = models.ManyToManyField(CodingQuestion, related_name="candidate_assessments")
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    expires_at = models.DateTimeField()
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    duration_minutes = models.IntegerField(default=60) # assessment duration
    
    # Store submission data: {"question_id": {"code": "...", "language": "...", "submitted_at": "..."}}
    submissions = models.JSONField(default=dict, blank=True)
    
    # Store grading output: {"question_id": {"passed_cases": 2, "total_cases": 5, "status": "Passed/Failed", "details": [...]}}
    results = models.JSONField(default=dict, blank=True)

    def is_expired(self):
        return timezone.now() > self.expires_at

    def has_time_remaining(self):
        if not self.started_at:
            return True
        elapsed = (timezone.now() - self.started_at).total_seconds() / 60
        return elapsed < self.duration_minutes

    def __str__(self):
        return f"Assessment for {self.candidate.email} - {self.job.title}"
