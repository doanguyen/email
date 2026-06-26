from django.db import models

from emailmarketing.accounts.models import GoogleAccount
from emailmarketing.common.models import BaseModel


class Campaign(BaseModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    name = models.CharField(max_length=255)
    subject = models.TextField()
    label = models.CharField(max_length=255)
    body_template = models.TextField()
    account = models.ForeignKey(
        GoogleAccount,
        on_delete=models.PROTECT,
        related_name="campaigns",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    total_contacts = models.IntegerField(default=0)
    sent_count = models.IntegerField(default=0)
    failed_count = models.IntegerField(default=0)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ["-created_at"]


class Contact(BaseModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"
        BOUNCED = "bounced", "Bounced"

    campaign = models.ForeignKey(
        Campaign,
        on_delete=models.CASCADE,
        related_name="contacts",
    )
    email = models.EmailField()
    first_name = models.CharField(max_length=255)
    attributes = models.JSONField(default=dict)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    sent_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)

    def __str__(self):
        return f"{self.email} ({self.campaign.name})"

    class Meta:
        ordering = ["created_at"]
