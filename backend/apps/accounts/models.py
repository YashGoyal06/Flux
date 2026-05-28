from django.db import models


class UserAccount(models.Model):
    name = models.CharField(max_length=255)
    username = models.CharField(max_length=255, unique=True)
    password = models.CharField(max_length=255)
    token = models.CharField(max_length=80, blank=True, null=True, db_index=True)
    google_id = models.CharField(max_length=255, unique=True, blank=True, null=True)
    profile_picture = models.URLField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.username


class Meeting(models.Model):
    user = models.ForeignKey(UserAccount, on_delete=models.CASCADE, related_name="meetings")
    meeting_code = models.CharField(max_length=255)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date"]

    def __str__(self):
        return f"{self.user.username} - {self.meeting_code}"
