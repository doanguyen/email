from celery import shared_task
from celery.utils.log import get_task_logger
from django.db.models import F

logger = get_task_logger(__name__)


def _campaign_send_failure(self, exc, task_id, args, kwargs, einfo):
    campaign_id = args[0]
    try:
        from emailmarketing.campaigns.models import Campaign
        from emailmarketing.campaigns.services import campaign_mark_failed

        campaign = Campaign.objects.get(id=campaign_id)
        campaign_mark_failed(campaign=campaign)
    except Exception:
        pass


@shared_task(bind=True, on_failure=_campaign_send_failure)
def campaign_send(self, campaign_id):
    from emailmarketing.accounts.services import account_get_gmail_service
    from emailmarketing.campaigns.models import Campaign, Contact
    from emailmarketing.campaigns.services import campaign_get_or_create_label, email_send

    campaign = Campaign.objects.select_related("account").get(id=campaign_id)
    campaign.status = Campaign.Status.RUNNING
    campaign.save(update_fields=["status", "updated_at"])

    try:
        gmail_service = account_get_gmail_service(account=campaign.account)
        label_id = campaign_get_or_create_label(
            gmail_service=gmail_service,
            label_name=campaign.label,
        )

        pending_contacts = Contact.objects.filter(
            campaign=campaign,
            status=Contact.Status.PENDING,
        )

        for contact in pending_contacts:
            try:
                email_send(
                    contact=contact,
                    gmail_service=gmail_service,
                    label_id=label_id,
                    subject=campaign.subject,
                    body_template=campaign.body_template,
                    sender_email=campaign.account.email,
                )
                Campaign.objects.filter(pk=campaign.pk).update(sent_count=F("sent_count") + 1)
            except Exception as exc:
                logger.warning(f"Failed to send to {contact.email}: {exc}")
                contact.status = Contact.Status.FAILED
                contact.error_message = str(exc)
                contact.save(update_fields=["status", "error_message", "updated_at"])
                Campaign.objects.filter(pk=campaign.pk).update(failed_count=F("failed_count") + 1)

        campaign.status = Campaign.Status.COMPLETED
        campaign.save(update_fields=["status", "updated_at"])

    except Exception as exc:
        logger.error(f"Campaign {campaign_id} failed with unhandled error: {exc}")
        raise
