from django.db import models
from django.utils import timezone
from jobs.models import Job, TenantModel

class Candidate(models.Model):
    # Candidate profiles are global or associated with a company.
    # To keep things clean, candidate contact details are global, but their applications are tenant-scoped.
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=50, blank=True, null=True)
    parsed_resume = models.JSONField(default=dict, blank=True) # Full parsed profile details
    confidence_score = models.FloatField(default=1.0)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

class Application(TenantModel):
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="applications")
    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE, related_name="applications")
    current_stage = models.CharField(max_length=100, default="Applied")
    cover_letter = models.TextField(blank=True, null=True)
    resume_file = models.CharField(max_length=1000, blank=True, default='')  # Supabase Storage URL
    internal_notes = models.JSONField(default=list, blank=True) # [{"recruiter": "Mark", "note": "text", "date": "..."}]
    status = models.CharField(max_length=50, default="Active") # Active, Offered, Hired, Rejected
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.candidate} - {self.job.title} ({self.company.name})"

class CandidateLogin(models.Model):
    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE, related_name="logins")
    login_date = models.DateField(default=timezone.now)

    class Meta:
        unique_together = ('candidate', 'login_date')

    def __str__(self):
        return f"{self.candidate.email} logged in on {self.login_date}"

