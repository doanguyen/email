from django.db import models

from emailmarketing.common.models import BaseModel


class GoogleAccount(BaseModel):
    email = models.EmailField(unique=True)
    credentials_json = models.JSONField()
    is_broken = models.BooleanField(default=False)

    def __str__(self):
        return self.email

    class Meta:
        ordering = ["-created_at"]
