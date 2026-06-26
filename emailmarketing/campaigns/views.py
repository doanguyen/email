from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from emailmarketing.accounts.selectors import account_get, account_list
from emailmarketing.campaigns.models import Campaign
from emailmarketing.campaigns.selectors import campaign_list, contact_list
from emailmarketing.campaigns.services import (
    campaign_create,
    campaign_parse_contacts,
    campaign_validate_template,
)


class HomeView(View):
    def get(self, request):
        return render(
            request,
            "home.html",
            {
                "accounts": account_list(),
                "campaigns": campaign_list(),
            },
        )


class CampaignCreateView(View):
    def get(self, request):
        account_id = request.GET.get("account")
        selected_account = None
        if account_id:
            try:
                selected_account = account_get(pk=int(account_id))
            except Exception:
                pass

        return render(
            request,
            "campaigns/create.html",
            {
                "accounts": account_list(),
                "selected_account": selected_account,
            },
        )

    def post(self, request):
        name = request.POST.get("name", "").strip()
        subject = request.POST.get("subject", "").strip()
        label = request.POST.get("label", "").strip()
        body_template = request.POST.get("body_template", "").strip()
        account_id = request.POST.get("account_id", "").strip()
        contacts_file = request.FILES.get("contacts")

        errors = []

        if not name:
            errors.append("Campaign name is required.")
        if not subject:
            errors.append("Subject is required.")
        if not label:
            errors.append("Label is required.")
        if not body_template:
            errors.append("Body template is required.")
        if not account_id:
            errors.append("Account is required.")
        if not contacts_file:
            errors.append("Contacts CSV file is required.")

        if not errors:
            try:
                campaign_validate_template(subject)
            except ValidationError as exc:
                errors.append(f"Subject: {exc.message}")

            try:
                campaign_validate_template(body_template)
            except ValidationError as exc:
                errors.append(f"Body template: {exc.message}")

        contacts_data = []
        if not errors and contacts_file:
            try:
                contacts_data = campaign_parse_contacts(contacts_file)
            except ValidationError as exc:
                errors.append(exc.message)

        account = None
        if not errors and account_id:
            try:
                account = account_get(pk=int(account_id))
            except Exception:
                errors.append("Selected account not found.")

        if errors:
            return render(
                request,
                "campaigns/create.html",
                {
                    "accounts": account_list(),
                    "errors": errors,
                    "form_data": {
                        "name": name,
                        "subject": subject,
                        "label": label,
                        "body_template": body_template,
                        "account_id": account_id,
                    },
                },
            )

        try:
            campaign = campaign_create(
                name=name,
                subject=subject,
                label=label,
                body_template=body_template,
                account=account,
                contacts_data=contacts_data,
            )
            messages.success(
                request,
                f"Campaign '{campaign.name}' created with {campaign.total_contacts} contacts. Sending started.",
            )
            return redirect("campaign-detail", pk=campaign.pk)
        except ValidationError as exc:
            return render(
                request,
                "campaigns/create.html",
                {
                    "accounts": account_list(),
                    "errors": [str(exc)],
                    "form_data": {
                        "name": name,
                        "subject": subject,
                        "label": label,
                        "body_template": body_template,
                        "account_id": account_id,
                    },
                },
            )


class CampaignDetailView(View):
    def get(self, request, pk):
        campaign = get_object_or_404(Campaign.objects.select_related("account"), pk=pk)
        contacts = contact_list(campaign=campaign)
        return render(
            request,
            "campaigns/detail.html",
            {
                "campaign": campaign,
                "contacts": contacts,
            },
        )


class CampaignStatusView(View):
    def get(self, request, pk):
        campaign = get_object_or_404(Campaign, pk=pk)
        return JsonResponse(
            {
                "status": campaign.status,
                "total_contacts": campaign.total_contacts,
                "sent_count": campaign.sent_count,
                "failed_count": campaign.failed_count,
            }
        )
