from django.contrib import admin

from emailmarketing.campaigns.models import Campaign, Contact


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ["name", "account", "status", "total_contacts", "sent_count", "failed_count", "created_at"]
    list_filter = ["status", "account"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ["email", "first_name", "campaign", "status", "sent_at"]
    list_filter = ["status", "campaign"]
    readonly_fields = ["created_at", "updated_at"]
