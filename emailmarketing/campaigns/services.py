import base64
import csv
import io
import json
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import IO

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from jinja2 import Environment, TemplateSyntaxError, meta

from emailmarketing.accounts.models import GoogleAccount
from emailmarketing.campaigns.models import Blacklist, Campaign, Contact, ContactSend, Touch

ALLOWED_TEMPLATE_VARS = {"first_name"}

_jinja_env = Environment()


def campaign_validate_template(template_str: str) -> None:
    try:
        ast = _jinja_env.parse(template_str)
    except TemplateSyntaxError as exc:
        raise ValidationError(f"Invalid template syntax: {exc}")

    variables = meta.find_undeclared_variables(ast)
    unsupported = variables - ALLOWED_TEMPLATE_VARS
    if unsupported:
        raise ValidationError(
            f"Template contains unsupported variables: {', '.join(sorted(unsupported))}. "
            f"Only {', '.join(sorted(ALLOWED_TEMPLATE_VARS))} is allowed."
        )


def campaign_parse_contacts(csv_file: IO) -> list[dict]:
    content = csv_file.read()
    if isinstance(content, bytes):
        content = content.decode("utf-8")

    reader = csv.DictReader(io.StringIO(content))
    fieldnames = set(reader.fieldnames or [])

    if not {"email", "name"}.issubset(fieldnames):
        raise ValidationError("CSV must have 'email' and 'name' columns.")

    seen = set()
    contacts = []
    for row in reader:
        email = row.get("email", "").strip()
        name = row.get("name", "").strip()

        if not email or email in seen:
            continue
        seen.add(email)

        first_name = name.split()[0] if name else email.split("@")[0]

        attributes = {}
        attr_str = row.get("attributes", "")
        if attr_str:
            try:
                attributes = json.loads(attr_str)
            except (json.JSONDecodeError, ValueError):
                pass

        contacts.append({"email": email, "first_name": first_name, "attributes": attributes})

    if not contacts:
        raise ValidationError("CSV file contains no valid contacts.")

    return contacts


@transaction.atomic
def campaign_create(
    *,
    name: str,
    label: str,
    subject: str,
    body_template: str,
    account: GoogleAccount,
    contacts_data: list[dict],
) -> Campaign:
    emails = [c["email"] for c in contacts_data]
    existing = Contact.objects.filter(account=account, email__in=emails).values_list("email", flat=True)
    if existing:
        raise ValidationError(
            f"The following emails are already used by this account: {', '.join(sorted(existing))}."
        )

    campaign = Campaign(
        name=name,
        account=account,
        status=Campaign.Status.PENDING,
        total_contacts=len(contacts_data),
    )
    campaign.full_clean()
    campaign.save()

    contacts = Contact.objects.bulk_create(
        [
            Contact(
                campaign=campaign,
                account=account,
                email=c["email"],
                first_name=c["first_name"],
                attributes=c["attributes"],
            )
            for c in contacts_data
        ]
    )

    touch = Touch(
        campaign=campaign,
        order=1,
        label=label,
        subject=subject,
        body_template=body_template,
        status=Touch.Status.PENDING,
        total_contacts=len(contacts),
    )
    touch.full_clean()
    touch.save()

    ContactSend.objects.bulk_create(
        [ContactSend(touch=touch, contact=c) for c in contacts]
    )

    transaction.on_commit(lambda: _queue_touch_send(touch.id))

    return campaign


@transaction.atomic
def touch_create(*, campaign: Campaign, label: str, subject: str, body_template: str) -> Touch:
    last_touch = campaign.touches.order_by("-order").first()
    if last_touch is None:
        raise ValidationError("Campaign has no touches.")
    if last_touch.status != Touch.Status.COMPLETED:
        raise ValidationError("The previous touch must be completed before adding a new one.")

    sent_contact_ids = ContactSend.objects.filter(
        touch=last_touch,
        status=ContactSend.Status.SENT,
    ).values_list("contact_id", flat=True)

    if not sent_contact_ids:
        raise ValidationError("No contacts were successfully sent in the previous touch.")

    touch = Touch(
        campaign=campaign,
        order=last_touch.order + 1,
        label=label,
        subject=subject,
        body_template=body_template,
        status=Touch.Status.PENDING,
        total_contacts=len(sent_contact_ids),
    )
    touch.full_clean()
    touch.save()

    sent_contacts = Contact.objects.filter(id__in=sent_contact_ids)
    ContactSend.objects.bulk_create(
        [ContactSend(touch=touch, contact=c) for c in sent_contacts]
    )

    transaction.on_commit(lambda: _queue_touch_send(touch.id))

    return touch


def campaign_mark_failed(*, campaign: Campaign) -> Campaign:
    campaign.status = Campaign.Status.FAILED
    campaign.save(update_fields=["status", "updated_at"])
    return campaign


def touch_mark_failed(*, touch: Touch) -> Touch:
    touch.status = Touch.Status.FAILED
    touch.save(update_fields=["status", "updated_at"])
    campaign_mark_failed(campaign=touch.campaign)
    return touch


def campaign_get_or_create_label(*, gmail_service, label_name: str) -> str:
    labels_response = gmail_service.users().labels().list(userId="me").execute()
    for label in labels_response.get("labels", []):
        if label["name"] == label_name:
            return label["id"]

    new_label = gmail_service.users().labels().create(
        userId="me",
        body={
            "name": label_name,
            "labelListVisibility": "labelShow",
            "messageListVisibility": "show",
        },
    ).execute()
    return new_label["id"]


def email_send(
    *,
    contact_send: ContactSend,
    gmail_service,
    label_id: str,
    sender_email: str,
    thread_id: str | None = None,
) -> ContactSend:
    contact = contact_send.contact
    touch = contact_send.touch

    rendered_subject = _jinja_env.from_string(touch.subject).render(first_name=contact.first_name)
    rendered_body = _jinja_env.from_string(touch.body_template).render(first_name=contact.first_name)

    message = MIMEMultipart("alternative")
    message["Subject"] = rendered_subject
    message["From"] = sender_email
    message["To"] = contact.email
    message.attach(MIMEText(rendered_body, "plain"))

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")

    body = {"raw": raw}
    if thread_id:
        body["threadId"] = thread_id

    sent = gmail_service.users().messages().send(userId="me", body=body).execute()

    gmail_service.users().messages().modify(
        userId="me",
        id=sent["id"],
        body={"addLabelIds": [label_id]},
    ).execute()

    contact_send.status = ContactSend.Status.SENT
    contact_send.sent_at = timezone.now()
    contact_send.gmail_message_id = sent["id"]
    contact_send.gmail_thread_id = sent.get("threadId", "")
    contact_send.save(update_fields=["status", "sent_at", "gmail_message_id", "gmail_thread_id", "updated_at"])

    return contact_send


def blacklist_add(*, email: str, reason: str = "") -> Blacklist:
    entry, _ = Blacklist.objects.get_or_create(email=email.strip().lower(), defaults={"reason": reason})
    return entry


def blacklist_remove(*, email: str) -> None:
    Blacklist.objects.filter(email=email.strip().lower()).delete()


def _queue_touch_send(touch_id: int) -> None:
    from emailmarketing.campaigns.tasks import touch_send

    touch_send.delay(touch_id)
