from django.conf import settings
from django.contrib import messages
from django.shortcuts import redirect
from django.views import View

from emailmarketing.accounts.services import account_create_from_oauth, account_get_oauth_url


class AccountOAuthStartView(View):
    def get(self, request):
        redirect_uri = settings.GOOGLE_OAUTH_REDIRECT_URI
        auth_url, state, code_verifier = account_get_oauth_url(redirect_uri=redirect_uri)
        request.session["oauth_state"] = state
        request.session["oauth_code_verifier"] = code_verifier
        return redirect(auth_url)


class AccountOAuthCallbackView(View):
    def get(self, request):
        code = request.GET.get("code")
        state = request.GET.get("state")
        stored_state = request.session.get("oauth_state")

        if not code or state != stored_state:
            messages.error(request, "OAuth failed: invalid state or missing code.")
            return redirect("home")

        try:
            redirect_uri = settings.GOOGLE_OAUTH_REDIRECT_URI
            code_verifier = request.session.get("oauth_code_verifier", "")
            account = account_create_from_oauth(
                code=code,
                state=state,
                redirect_uri=redirect_uri,
                code_verifier=code_verifier,
            )
            messages.success(request, f"Account {account.email} added successfully.")
        except Exception as exc:
            messages.error(request, f"Failed to add account: {exc}")

        return redirect("home")
