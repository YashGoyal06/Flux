from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class Company(models.Model):
    name = models.CharField(max_length=255)
    domain = models.CharField(max_length=255, unique=True, blank=True, null=True)
    logo_url = models.URLField(max_length=1000, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    industry = models.CharField(max_length=100, blank=True, null=True)
    size = models.CharField(max_length=50, blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.name

class TenantModel(models.Model):
    """
    Abstract base model that enforces multi-tenancy by linking to a Company.
    """
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="%(class)ss")

    class Meta:
        abstract = True

class RecruiterToken(TenantModel):
    email = models.EmailField()
    token_hash = models.CharField(max_length=64, unique=True)  # SHA-256 hash of the token
    is_used = models.BooleanField(default=False)
    is_revoked = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()

    def has_expired(self):
        return timezone.now() > self.expires_at

    def __str__(self):
        return f"Token for {self.email} ({self.company.name})"

class RecruiterProfile(TenantModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="recruiter_profile")
    full_name = models.CharField(max_length=255)
    job_title = models.CharField(max_length=255, blank=True, null=True)
    department = models.CharField(max_length=100, blank=True, null=True)
    phone_number = models.CharField(max_length=50, blank=True, null=True)
    linkedin_url = models.URLField(max_length=1000, blank=True, null=True)
    specialization_areas = models.JSONField(default=list, blank=True)
    years_of_experience = models.CharField(max_length=50, blank=True, null=True)
    bio = models.TextField(blank=True, null=True)
    preferred_timezone = models.CharField(max_length=100, default='UTC')
    notification_preferences = models.JSONField(default=dict, blank=True)
    photo_url = models.URLField(max_length=1000, blank=True, null=True)
    passing_ats_score = models.IntegerField(default=70)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.full_name} ({self.company.name})"

class CompanyAdminProfile(TenantModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="admin_profile")
    photo_url = models.URLField(max_length=1000, blank=True, null=True)
    is_2fa_enabled = models.BooleanField(default=False)
    totp_secret = models.CharField(max_length=32, blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Admin: {self.user.email} ({self.company.name})"
