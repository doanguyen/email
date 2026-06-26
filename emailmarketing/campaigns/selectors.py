from typing import Iterable

from emailmarketing.campaigns.models import Campaign, Contact


def campaign_list() -> Iterable[Campaign]:
    return Campaign.objects.select_related("account").all()


def campaign_get(*, pk: int) -> Campaign:
    return Campaign.objects.select_related("account").get(pk=pk)


def contact_list(*, campaign: Campaign) -> Iterable[Contact]:
    return Contact.objects.filter(campaign=campaign)
