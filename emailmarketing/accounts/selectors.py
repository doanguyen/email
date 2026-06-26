from typing import Iterable

from emailmarketing.accounts.models import GoogleAccount


def account_list() -> Iterable[GoogleAccount]:
    return GoogleAccount.objects.all()


def account_get(*, pk: int) -> GoogleAccount:
    return GoogleAccount.objects.get(pk=pk)
