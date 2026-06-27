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

    def __str__(self):
        return self.name

    class Meta:
        ordering = ["-created_at"]


class Touch(BaseModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    campaign = models.ForeignKey(
        Campaign,
        on_delete=models.CASCADE,
        related_name="touches",
    )
    order = models.PositiveIntegerField()
    label = models.CharField(max_length=255)
    subject = models.TextField()
    body_template = models.TextField()
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    sent_count = models.IntegerField(default=0)
    failed_count = models.IntegerField(default=0)
    total_contacts = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.campaign.name} — Touch {self.order}"

    class Meta:
        ordering = ["order"]
        unique_together = [["campaign", "order"]]


class Contact(BaseModel):
    campaign = models.ForeignKey(
        Campaign,
        on_delete=models.CASCADE,
        related_name="contacts",
    )
    account = models.ForeignKey(
        GoogleAccount,
        on_delete=models.PROTECT,
        related_name="contacts",
    )
    email = models.EmailField()
    first_name = models.CharField(max_length=255)
    attributes = models.JSONField(default=dict)

    def __str__(self):
        return f"{self.email} ({self.campaign.name})"

    class Meta:
        ordering = ["created_at"]
        unique_together = [["account", "email"]]


class ContactSend(BaseModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"
        SKIPPED = "skipped", "Skipped"

    touch = models.ForeignKey(
        Touch,
        on_delete=models.CASCADE,
        related_name="contact_sends",
    )
    contact = models.ForeignKey(
        Contact,
        on_delete=models.CASCADE,
        related_name="sends",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    sent_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    gmail_message_id = models.CharField(max_length=255, blank=True)
    gmail_thread_id = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["created_at"]
        unique_together = [["touch", "contact"]]


class Blacklist(BaseModel):
    email = models.EmailField(unique=True)
    reason = models.TextField(blank=True)

    def __str__(self):
        return self.email

    class Meta:
        ordering = ["email"]
