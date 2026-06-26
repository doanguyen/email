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
from emailmarketing.campaigns.models import Campaign, Contact

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

    contacts = []
    for row in reader:
        email = row.get("email", "").strip()
        name = row.get("name", "").strip()

        if not email:
            continue

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
    subject: str,
    label: str,
    body_template: str,
    account: GoogleAccount,
    contacts_data: list[dict],
) -> Campaign:
    campaign = Campaign(
        name=name,
        subject=subject,
        label=label,
        body_template=body_template,
        account=account,
        status=Campaign.Status.PENDING,
        total_contacts=len(contacts_data),
    )
    campaign.full_clean()
    campaign.save()

    Contact.objects.bulk_create(
        [
            Contact(
                campaign=campaign,
                email=c["email"],
                first_name=c["first_name"],
                attributes=c["attributes"],
            )
            for c in contacts_data
        ]
    )

    transaction.on_commit(lambda: _queue_campaign_send(campaign.id))

    return campaign


def campaign_mark_failed(*, campaign: Campaign) -> Campaign:
    campaign.status = Campaign.Status.FAILED
    campaign.save(update_fields=["status", "updated_at"])
    return campaign


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
    contact: Contact,
    gmail_service,
    label_id: str,
    subject: str,
    body_template: str,
    sender_email: str,
) -> Contact:
    rendered_subject = _jinja_env.from_string(subject).render(first_name=contact.first_name)
    rendered_body = _jinja_env.from_string(body_template).render(first_name=contact.first_name)

    message = MIMEMultipart("alternative")
    message["Subject"] = rendered_subject
    message["From"] = sender_email
    message["To"] = contact.email
    message.attach(MIMEText(rendered_body, "plain"))

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")

    sent = gmail_service.users().messages().send(
        userId="me",
        body={"raw": raw},
    ).execute()

    gmail_service.users().messages().modify(
        userId="me",
        id=sent["id"],
        body={"addLabelIds": [label_id]},
    ).execute()

    contact.status = Contact.Status.SENT
    contact.sent_at = timezone.now()
    contact.save(update_fields=["status", "sent_at", "updated_at"])

    return contact


def _queue_campaign_send(campaign_id: int) -> None:
    from emailmarketing.campaigns.tasks import campaign_send

    campaign_send.delay(campaign_id)
