import json
import os

from django.conf import settings

os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")
from django.core.exceptions import ValidationError

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

from emailmarketing.accounts.models import GoogleAccount


def account_get_oauth_url(*, redirect_uri: str) -> tuple[str, str, str]:
    flow = Flow.from_client_secrets_file(
        settings.GOOGLE_OAUTH_CREDENTIALS_FILE,
        scopes=settings.GOOGLE_OAUTH_SCOPES,
        redirect_uri=redirect_uri,
    )
    auth_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    assert flow.code_verifier is not None
    return auth_url, state, flow.code_verifier


def account_create_from_oauth(*, code: str, state: str, redirect_uri: str, code_verifier: str) -> GoogleAccount:
    flow = Flow.from_client_secrets_file(
        settings.GOOGLE_OAUTH_CREDENTIALS_FILE,
        scopes=settings.GOOGLE_OAUTH_SCOPES,
        state=state,
        redirect_uri=redirect_uri,
    )
    flow.fetch_token(code=code, code_verifier=code_verifier)
    credentials = flow.credentials

    email = _get_sender_email(credentials)
    credentials_data = json.loads(credentials.to_json())

    account, _ = GoogleAccount.objects.update_or_create(
        email=email,
        defaults={
            "credentials_json": credentials_data,
            "is_broken": False,
        },
    )
    return account


def account_refresh_credentials(*, account: GoogleAccount) -> Credentials:
    credentials = Credentials.from_authorized_user_info(account.credentials_json)

    if credentials.expired and credentials.refresh_token:
        try:
            credentials.refresh(Request())
            account.credentials_json = json.loads(credentials.to_json())
            account.is_broken = False
            account.save(update_fields=["credentials_json", "is_broken", "updated_at"])
        except Exception:
            account.is_broken = True
            account.save(update_fields=["is_broken", "updated_at"])
            raise ValidationError(f"Failed to refresh credentials for {account.email}")

    return credentials


def account_get_gmail_service(*, account: GoogleAccount):
    credentials = account_refresh_credentials(account=account)
    return build("gmail", "v1", credentials=credentials)


def _get_sender_email(credentials: Credentials) -> str:
    service = build("gmail", "v1", credentials=credentials)
    profile = service.users().getProfile(userId="me").execute()
    return profile["emailAddress"]
