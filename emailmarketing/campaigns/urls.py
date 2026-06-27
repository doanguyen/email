from django.urls import path

from emailmarketing.campaigns.views import (
    BlacklistView,
    CampaignCreateView,
    CampaignDetailView,
    CampaignStatusView,
    TouchCreateView,
)

urlpatterns = [
    path("create/", CampaignCreateView.as_view(), name="campaign-create"),
    path("<int:pk>/", CampaignDetailView.as_view(), name="campaign-detail"),
    path("<int:pk>/status/", CampaignStatusView.as_view(), name="campaign-status"),
    path("<int:campaign_pk>/touches/create/", TouchCreateView.as_view(), name="touch-create"),
    path("blacklist/", BlacklistView.as_view(), name="blacklist"),
]
