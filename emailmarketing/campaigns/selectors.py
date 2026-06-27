from typing import Iterable

from emailmarketing.campaigns.models import Blacklist, Campaign, Contact, ContactSend, Touch


def campaign_list() -> Iterable[Campaign]:
    return Campaign.objects.select_related("account").all()


def campaign_get(*, pk: int) -> Campaign:
    return Campaign.objects.select_related("account").get(pk=pk)


def touch_list(*, campaign: Campaign) -> Iterable[Touch]:
    return Touch.objects.filter(campaign=campaign)


def touch_get(*, pk: int) -> Touch:
    return Touch.objects.select_related("campaign__account").get(pk=pk)


def contact_list(*, campaign: Campaign) -> Iterable[Contact]:
    return Contact.objects.filter(campaign=campaign)


def contact_send_list(*, touch: Touch) -> Iterable[ContactSend]:
    return ContactSend.objects.filter(touch=touch).select_related("contact")


def blacklist_list() -> Iterable[Blacklist]:
    return Blacklist.objects.all()
