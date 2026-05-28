from django.db import models

class TestCredential(models.Model):
    role = models.CharField(max_length=50) # 'recruiter', 'candidate', 'admin'
    label = models.CharField(max_length=100) # e.g. 'Enterprise Admin', 'Recruiter Lead'
    email = models.EmailField()
    password = models.CharField(max_length=255) # token or password

    def __str__(self):
        return f"{self.label} ({self.role})"
