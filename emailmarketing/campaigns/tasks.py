from celery import shared_task
from celery.utils.log import get_task_logger
from django.db.models import F

logger = get_task_logger(__name__)


def _touch_send_failure(self, exc, task_id, args, kwargs, einfo):
    touch_id = args[0]
    try:
        from emailmarketing.campaigns.models import Touch
        from emailmarketing.campaigns.services import touch_mark_failed

        touch = Touch.objects.select_related("campaign").get(id=touch_id)
        touch_mark_failed(touch=touch)
    except Exception:
        pass


@shared_task(bind=True, on_failure=_touch_send_failure)
def touch_send(self, touch_id):
    from emailmarketing.accounts.services import account_get_gmail_service
    from emailmarketing.campaigns.models import Blacklist, Campaign, ContactSend, Touch
    from emailmarketing.campaigns.services import campaign_get_or_create_label, email_send

    touch = Touch.objects.select_related("campaign__account").get(id=touch_id)
    campaign = touch.campaign

    touch.status = Touch.Status.RUNNING
    touch.save(update_fields=["status", "updated_at"])
    campaign.status = Campaign.Status.RUNNING
    campaign.save(update_fields=["status", "updated_at"])

    blacklisted_emails = set(
        Blacklist.objects.values_list("email", flat=True)
    )

    try:
        gmail_service = account_get_gmail_service(account=campaign.account)
        label_id = campaign_get_or_create_label(
            gmail_service=gmail_service,
            label_name=touch.label,
        )

        pending_sends = ContactSend.objects.filter(
            touch=touch,
            status=ContactSend.Status.PENDING,
        ).select_related("contact")

        for contact_send in pending_sends:
            contact = contact_send.contact

            if contact.email in blacklisted_emails:
                contact_send.status = ContactSend.Status.SKIPPED
                contact_send.error_message = "Email is blacklisted"
                contact_send.save(update_fields=["status", "error_message", "updated_at"])
                Touch.objects.filter(pk=touch.pk).update(failed_count=F("failed_count") + 1)
                continue

            thread_id = None
            if touch.order > 1:
                prev_send = ContactSend.objects.filter(
                    touch__campaign=campaign,
                    touch__order=touch.order - 1,
                    contact=contact,
                    status=ContactSend.Status.SENT,
                ).first()
                if prev_send:
                    thread_id = prev_send.gmail_thread_id or None

            try:
                email_send(
                    contact_send=contact_send,
                    gmail_service=gmail_service,
                    label_id=label_id,
                    sender_email=campaign.account.email,
                    thread_id=thread_id,
                )
                Touch.objects.filter(pk=touch.pk).update(sent_count=F("sent_count") + 1)
            except Exception as exc:
                logger.warning(f"Failed to send to {contact.email}: {exc}")
                contact_send.status = ContactSend.Status.FAILED
                contact_send.error_message = str(exc)
                contact_send.save(update_fields=["status", "error_message", "updated_at"])
                Touch.objects.filter(pk=touch.pk).update(failed_count=F("failed_count") + 1)

        touch.status = Touch.Status.COMPLETED
        touch.save(update_fields=["status", "updated_at"])
        campaign.status = Campaign.Status.COMPLETED
        campaign.save(update_fields=["status", "updated_at"])

    except Exception as exc:
        logger.error(f"Touch {touch_id} failed with unhandled error: {exc}")
        raise
