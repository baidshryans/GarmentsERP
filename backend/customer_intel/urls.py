"""URL routes for the Customer 360 app, mounted at /customer-intel/."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from customer_intel import views, webhook_views

router = DefaultRouter()
router.register(r"api/tags", views.CustomerTagViewSet, basename="customer-tag")
router.register(r"api/segments", views.SegmentViewSet, basename="segment")
router.register(r"api/templates", views.MessageTemplateViewSet, basename="message-template")
router.register(r"api/campaigns", views.CampaignViewSet, basename="campaign")

urlpatterns = [
    path("api/customers/", views.CustomerListView.as_view(), name="ci-customers"),
    path("api/worklist/", views.WorklistView.as_view(), name="ci-worklist"),
    path("api/customers/<int:ledger_id>/profile/",
         views.CustomerProfileView.as_view(), name="ci-customer-profile"),
    path("api/customers/<int:ledger_id>/timeline/",
         views.CustomerTimelineView.as_view(), name="ci-customer-timeline"),
    path("api/customers/<int:ledger_id>/note/",
         views.CustomerNoteView.as_view(), name="ci-customer-note"),
    path("api/customers/<int:ledger_id>/social/",
         views.CustomerSocialProfileView.as_view(), name="ci-customer-social"),
    path("api/customers/<int:ledger_id>/opt-out/",
         views.CustomerOptOutView.as_view(), name="ci-customer-opt-out"),
    path("api/customers/<int:ledger_id>/tags/",
         views.CustomerTagsView.as_view(), name="ci-customer-tags"),

    # Public, unauthenticated. Guarded by a per-retail path key plus an HMAC
    # signature check — see webhook_views for why both are needed.
    path("api/whatsapp/webhook/<str:url_key>/",
         webhook_views.WhatsAppWebhookView.as_view(), name="ci-whatsapp-webhook"),

    path("", include(router.urls)),
]
