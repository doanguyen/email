from django.contrib import admin

from emailmarketing.accounts.models import GoogleAccount


@admin.register(GoogleAccount)
class GoogleAccountAdmin(admin.ModelAdmin):
    list_display = ["email", "is_broken", "created_at"]
    list_filter = ["is_broken"]
    readonly_fields = ["credentials_json", "created_at", "updated_at"]
