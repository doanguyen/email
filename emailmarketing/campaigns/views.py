from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from emailmarketing.accounts.selectors import account_get, account_list
from emailmarketing.campaigns.models import Campaign, Touch
from emailmarketing.campaigns.selectors import (
    blacklist_list,
    campaign_list,
    contact_send_list,
    contact_list,
    touch_list,
)
from emailmarketing.campaigns.services import (
    blacklist_add,
    blacklist_remove,
    campaign_create,
    campaign_parse_contacts,
    campaign_validate_template,
    touch_create,
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
        label = request.POST.get("label", "").strip()
        subject = request.POST.get("subject", "").strip()
        body_template = request.POST.get("body_template", "").strip()
        account_id = request.POST.get("account_id", "").strip()
        contacts_file = request.FILES.get("contacts")

        errors = []

        if not name:
            errors.append("Campaign name is required.")
        if not label:
            errors.append("Label is required.")
        if not subject:
            errors.append("Subject is required.")
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
                        "label": label,
                        "subject": subject,
                        "body_template": body_template,
                        "account_id": account_id,
                    },
                },
            )

        try:
            campaign = campaign_create(
                name=name,
                label=label,
                subject=subject,
                body_template=body_template,
                account=account,
                contacts_data=contacts_data,
            )
            messages.success(
                request,
                f"Campaign '{campaign.name}' created with {campaign.total_contacts} contacts. Touch 1 sending started.",
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
                        "label": label,
                        "subject": subject,
                        "body_template": body_template,
                        "account_id": account_id,
                    },
                },
            )


class CampaignDetailView(View):
    def get(self, request, pk):
        campaign = get_object_or_404(Campaign.objects.select_related("account"), pk=pk)
        touches = list(touch_list(campaign=campaign))
        latest_touch = touches[-1] if touches else None
        contact_sends = list(contact_send_list(touch=latest_touch)) if latest_touch else []
        can_add_touch = latest_touch is not None and latest_touch.status == Touch.Status.COMPLETED
        return render(
            request,
            "campaigns/detail.html",
            {
                "campaign": campaign,
                "touches": touches,
                "latest_touch": latest_touch,
                "contact_sends": contact_sends,
                "can_add_touch": can_add_touch,
            },
        )


class CampaignStatusView(View):
    def get(self, request, pk):
        campaign = get_object_or_404(Campaign, pk=pk)
        touches_data = [
            {
                "id": t.id,
                "order": t.order,
                "status": t.status,
                "sent_count": t.sent_count,
                "failed_count": t.failed_count,
                "total_contacts": t.total_contacts,
            }
            for t in touch_list(campaign=campaign)
        ]
        return JsonResponse(
            {
                "campaign_status": campaign.status,
                "total_contacts": campaign.total_contacts,
                "touches": touches_data,
            }
        )


class TouchCreateView(View):
    def get(self, request, campaign_pk):
        campaign = get_object_or_404(Campaign.objects.select_related("account"), pk=campaign_pk)
        last_touch = campaign.touches.order_by("-order").first()
        if last_touch is None or last_touch.status != Touch.Status.COMPLETED:
            messages.error(request, "You can only add a touch after the previous one is completed.")
            return redirect("campaign-detail", pk=campaign_pk)
        return render(request, "campaigns/touch_create.html", {"campaign": campaign, "next_order": last_touch.order + 1})

    def post(self, request, campaign_pk):
        campaign = get_object_or_404(Campaign.objects.select_related("account"), pk=campaign_pk)
        label = request.POST.get("label", "").strip()
        subject = request.POST.get("subject", "").strip()
        body_template = request.POST.get("body_template", "").strip()

        errors = []
        if not label:
            errors.append("Label is required.")
        if not subject:
            errors.append("Subject is required.")
        if not body_template:
            errors.append("Body template is required.")

        if not errors:
            try:
                campaign_validate_template(subject)
            except ValidationError as exc:
                errors.append(f"Subject: {exc.message}")
            try:
                campaign_validate_template(body_template)
            except ValidationError as exc:
                errors.append(f"Body template: {exc.message}")

        last_touch = campaign.touches.order_by("-order").first()
        next_order = (last_touch.order + 1) if last_touch else 2

        if errors:
            return render(
                request,
                "campaigns/touch_create.html",
                {
                    "campaign": campaign,
                    "next_order": next_order,
                    "errors": errors,
                    "form_data": {"label": label, "subject": subject, "body_template": body_template},
                },
            )

        try:
            touch = touch_create(
                campaign=campaign,
                label=label,
                subject=subject,
                body_template=body_template,
            )
            messages.success(
                request,
                f"Touch {touch.order} created with {touch.total_contacts} recipients. Sending started.",
            )
            return redirect("campaign-detail", pk=campaign_pk)
        except ValidationError as exc:
            return render(
                request,
                "campaigns/touch_create.html",
                {
                    "campaign": campaign,
                    "next_order": next_order,
                    "errors": [str(exc)],
                    "form_data": {"label": label, "subject": subject, "body_template": body_template},
                },
            )


class BlacklistView(View):
    def get(self, request):
        return render(request, "blacklist/list.html", {"entries": blacklist_list()})

    def post(self, request):
        action = request.POST.get("action")
        email = request.POST.get("email", "").strip()

        if action == "add":
            if not email:
                messages.error(request, "Email is required.")
            else:
                reason = request.POST.get("reason", "").strip()
                blacklist_add(email=email, reason=reason)
                messages.success(request, f"{email} added to blacklist.")
        elif action == "remove":
            blacklist_remove(email=email)
            messages.success(request, f"{email} removed from blacklist.")

        return redirect("blacklist")
