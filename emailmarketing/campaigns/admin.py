from django.contrib import admin

from emailmarketing.campaigns.models import Blacklist, Campaign, Contact, ContactSend, Touch


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ["name", "account", "status", "total_contacts", "created_at"]
    list_filter = ["status", "account"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(Touch)
class TouchAdmin(admin.ModelAdmin):
    list_display = ["__str__", "campaign", "order", "status", "sent_count", "failed_count", "total_contacts"]
    list_filter = ["status", "campaign"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ["email", "first_name", "campaign", "account"]
    list_filter = ["campaign", "account"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(ContactSend)
class ContactSendAdmin(admin.ModelAdmin):
    list_display = ["contact", "touch", "status", "sent_at", "gmail_thread_id"]
    list_filter = ["status", "touch"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(Blacklist)
class BlacklistAdmin(admin.ModelAdmin):
    list_display = ["email", "reason", "created_at"]
    search_fields = ["email"]
    readonly_fields = ["created_at", "updated_at"]
