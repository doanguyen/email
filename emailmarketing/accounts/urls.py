from django.urls import path

from emailmarketing.accounts.views import AccountOAuthCallbackView, AccountOAuthStartView

urlpatterns = [
    path("add/", AccountOAuthStartView.as_view(), name="account-add"),
    path("oauth/callback/", AccountOAuthCallbackView.as_view(), name="account-oauth-callback"),
]
