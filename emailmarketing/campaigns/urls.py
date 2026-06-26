from django.urls import path

from emailmarketing.campaigns.views import CampaignCreateView, CampaignDetailView, CampaignStatusView

urlpatterns = [
    path("create/", CampaignCreateView.as_view(), name="campaign-create"),
    path("<int:pk>/", CampaignDetailView.as_view(), name="campaign-detail"),
    path("<int:pk>/status/", CampaignStatusView.as_view(), name="campaign-status"),
]
