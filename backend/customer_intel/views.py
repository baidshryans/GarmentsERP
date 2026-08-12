"""
Customer 360 API.

The analytics reads are plain APIViews (following the vendor_analytics pattern)
because they aggregate across several models and have no single queryset. That
means `RBACPermission` cannot protect them, so they use the model-anchored
`HasIntelAccess` from this app's permissions module instead. CRUD models keep
`RetailBaseViewset` with `fy_scoped = False` — snapshots and tags are
deliberately cross-fiscal-year.
"""

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from contacts.models import Ledger
from customer_intel.models import (
    CustomerProfileSnapshot,
    CustomerSocialProfile,
    CustomerTag,
    CustomerTagAssignment,
    Campaign,
    EngagementEvent,
    MessageTemplate,
    Segment,
)
from customer_intel.permissions import CanExportCustomerData, HasIntelAccess
from customer_intel.serializers import (
    CustomerListSerializer,
    CustomerNoteSerializer,
    CustomerSocialProfileSerializer,
    CustomerTagSerializer,
    CampaignRecipientSerializer,
    CampaignSerializer,
    EngagementEventSerializer,
    MessageTemplateSerializer,
    SegmentSerializer,
    TagAssignmentSerializer,
)
from customer_intel.services.profile import build_profile
from jewel_test.pagination_custom import CustomPagination
from userauth.utils import can_user_view_customer_data
from userauth.views import RetailBaseViewset

ORDERING_FIELDS = {
    "net_spend": "-net_spend",
    "-net_spend": "-net_spend",
    "lifetime_value": "-lifetime_value",
    "-lifetime_value": "-lifetime_value",
    "last_purchase_date": "-last_purchase_date",
    "-last_purchase_date": "-last_purchase_date",
    "days_since_last": "days_since_last",
    "-days_since_last": "-days_since_last",
    "engagement_score": "-engagement_score",
    "-engagement_score": "-engagement_score",
    "ac_name": "ledger__ac_name",
    "-ac_name": "-ledger__ac_name",
}
DEFAULT_ORDERING = "-net_spend"


def _retail(request):
    return getattr(request, "retail", None)


class CustomerListView(APIView):
    """
    GET /customer-intel/api/customers/

    Server-paged, filterable customer book backed by the nightly snapshot.
    Filters: q, rfm_segment, lapse_band, confidence, tag, city, b2b,
             min_spend, max_spend, silent_days, has_dob, ordering
    """

    permission_classes = [HasIntelAccess]

    def get(self, request):
        retail = _retail(request)
        if retail is None:
            return Response({"error": "No active retail on the request."},
                            status=status.HTTP_400_BAD_REQUEST)

        qs = (
            CustomerProfileSnapshot.objects
            .filter(retail=retail)
            .select_related("ledger")
        )

        params = request.query_params
        q = (params.get("q") or "").strip()
        if q:
            qs = qs.filter(
                Q(ledger__ac_name__icontains=q)
                | Q(ledger__display_name__icontains=q)
                | Q(ledger__mobile1__icontains=q)
                | Q(ledger__email__icontains=q)
            )

        for field in ("rfm_segment", "lapse_band", "confidence"):
            value = params.get(field)
            if value:
                qs = qs.filter(**{f"{field}__in": [v for v in value.split(",") if v]})

        if params.get("city"):
            qs = qs.filter(ledger__city__iexact=params["city"])
        if params.get("b2b") in ("true", "false"):
            qs = qs.filter(b2b=params["b2b"] == "true")
        if params.get("has_dob") == "true":
            qs = qs.filter(ledger__dob__isnull=False)
        elif params.get("has_dob") == "false":
            qs = qs.filter(ledger__dob__isnull=True)

        for param, lookup in (("min_spend", "net_spend__gte"),
                              ("max_spend", "net_spend__lte"),
                              ("silent_days", "days_since_last__gte")):
            raw = params.get(param)
            if raw:
                try:
                    qs = qs.filter(**{lookup: float(raw)})
                except ValueError:
                    return Response({"error": f"{param} must be numeric."},
                                    status=status.HTTP_400_BAD_REQUEST)

        tag = params.get("tag")
        if tag:
            tag_ids = [t for t in tag.split(",") if t.isdigit()]
            if tag_ids:
                qs = qs.filter(ledger__intel_tags__tag_id__in=tag_ids).distinct()

        # Customers who have never bought are noise for most workflows, but the
        # profile-completion drive needs them — so it is opt-in, not the default.
        if params.get("buyers_only", "true") == "true":
            qs = qs.filter(purchase_count_all__gt=0)

        ordering = ORDERING_FIELDS.get(params.get("ordering"), DEFAULT_ORDERING)
        qs = qs.order_by(ordering, "-id")

        paginator = CustomPagination()
        page = paginator.paginate_queryset(qs, request, view=self)

        # Tags are attached per page rather than joined into the main query, so
        # a customer with many tags cannot multiply the paginated row count.
        self._attach_tags(page)

        serializer = CustomerListSerializer(
            page, many=True,
            context={"mask_customers": not can_user_view_customer_data(request.user)},
        )
        return paginator.get_paginated_response(serializer.data)

    @staticmethod
    def _attach_tags(page):
        ledger_ids = [s.ledger_id for s in page]
        assignments = (
            CustomerTagAssignment.objects
            .filter(ledger_id__in=ledger_ids)
            .select_related("tag")
        )
        by_ledger = {}
        for assignment in assignments:
            by_ledger.setdefault(assignment.ledger_id, []).append(assignment)
        for snapshot in page:
            snapshot._prefetched_tags = by_ledger.get(snapshot.ledger_id, [])


class CustomerProfileView(APIView):
    """GET /customer-intel/api/customers/<ledger_id>/profile/"""

    permission_classes = [HasIntelAccess]

    def get(self, request, ledger_id):
        retail = _retail(request)
        ledger = get_object_or_404(
            Ledger.objects.filter(
                Q(retail_code=retail) | Q(retail_code__isnull=True),
            ),
            pk=ledger_id,
        )
        payload = build_profile(retail, ledger)

        if not can_user_view_customer_data(request.user):
            from contacts.masking import mask_ledger_representation
            payload["ledger"] = mask_ledger_representation(payload["ledger"], ledger)
        return Response(payload)


class CustomerTimelineView(APIView):
    """GET /customer-intel/api/customers/<ledger_id>/timeline/"""

    permission_classes = [HasIntelAccess]

    def get(self, request, ledger_id):
        retail = _retail(request)
        qs = (
            EngagementEvent.objects
            .filter(retail=retail, ledger_id=ledger_id)
            .select_related("created_by")
        )
        channel = request.query_params.get("channel")
        if channel:
            qs = qs.filter(channel__in=[c for c in channel.split(",") if c])

        paginator = CustomPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        return paginator.get_paginated_response(
            EngagementEventSerializer(page, many=True).data
        )


class CustomerNoteView(APIView):
    """POST /customer-intel/api/customers/<ledger_id>/note/"""

    permission_classes = [HasIntelAccess]

    def post(self, request, ledger_id):
        retail = _retail(request)
        ledger = get_object_or_404(Ledger, pk=ledger_id)

        serializer = CustomerNoteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        event = EngagementEvent.objects.create(
            retail=retail,
            ledger=ledger,
            channel=data["channel"],
            direction="out" if data["channel"] != "note" else "sys",
            event_type="manual_note",
            subject=data.get("subject", ""),
            body=data["body"],
            status="sent",
            occurred_at=timezone.now(),
            created_by=request.user,
        )
        return Response(EngagementEventSerializer(event).data,
                        status=status.HTTP_201_CREATED)


class CustomerSocialProfileView(APIView):
    """
    GET/PATCH /customer-intel/api/customers/<ledger_id>/social/

    Also accepts `dob` and `anniversary`, which live on Ledger rather than the
    social profile — this is the capture path used by the billing-screen prompt,
    and asking the caller to make two requests for one form would be silly.
    """

    permission_classes = [HasIntelAccess]

    def get(self, request, ledger_id):
        ledger = get_object_or_404(Ledger, pk=ledger_id)
        profile, _ = CustomerSocialProfile.objects.get_or_create(ledger=ledger)
        data = CustomerSocialProfileSerializer(profile).data
        data["dob"] = ledger.dob
        data["anniversary"] = ledger.anniversary
        return Response(data)

    def patch(self, request, ledger_id):
        ledger = get_object_or_404(Ledger, pk=ledger_id)
        profile, _ = CustomerSocialProfile.objects.get_or_create(ledger=ledger)

        ledger_updates = {}
        for field in ("dob", "anniversary"):
            if field in request.data:
                ledger_updates[field] = request.data[field] or None
        if ledger_updates:
            for field, value in ledger_updates.items():
                setattr(ledger, field, value)
            ledger.save(update_fields=list(ledger_updates))

        serializer = CustomerSocialProfileSerializer(
            profile, data=request.data, partial=True,
        )
        serializer.is_valid(raise_exception=True)
        if serializer.validated_data and not serializer.instance.consent_at:
            serializer.validated_data.setdefault("consent_source", "erp_form")
            serializer.validated_data.setdefault("consent_at", timezone.now())
        serializer.save()

        data = serializer.data
        data["dob"] = ledger.dob
        data["anniversary"] = ledger.anniversary
        return Response(data)


class CustomerOptOutView(APIView):
    """
    POST /customer-intel/api/customers/<ledger_id>/opt-out/

    Marketing is opt-out rather than opt-in for this retailer, which makes this
    endpoint load-bearing: it is the mechanism that keeps that position
    defensible. Opting out is recorded with a timestamp and reason and is
    honoured absolutely by every send path and every audience export.
    """

    permission_classes = [HasIntelAccess]

    def post(self, request, ledger_id):
        ledger = get_object_or_404(Ledger, pk=ledger_id)
        profile, _ = CustomerSocialProfile.objects.get_or_create(ledger=ledger)

        opt_back_in = str(request.data.get("opt_in", "")).lower() in ("1", "true")
        if opt_back_in:
            profile.opt_out_at = None
            profile.opt_out_reason = ""
            profile.whatsapp_opt_in = True
            profile.email_opt_in = True
        else:
            profile.opt_out_at = timezone.now()
            profile.opt_out_reason = (request.data.get("reason") or "")[:200]
            profile.whatsapp_opt_in = False
            profile.email_opt_in = False
        profile.save()

        EngagementEvent.objects.create(
            retail=_retail(request),
            ledger=ledger,
            channel="note",
            direction="sys",
            event_type="opt_in" if opt_back_in else "opt_out",
            subject="Marketing opt-in restored" if opt_back_in else "Opted out of marketing",
            body=profile.opt_out_reason,
            status="sent",
            occurred_at=timezone.now(),
            created_by=request.user,
        )
        return Response(CustomerSocialProfileSerializer(profile).data)


class CustomerTagsView(APIView):
    """POST / DELETE /customer-intel/api/customers/<ledger_id>/tags/"""

    permission_classes = [HasIntelAccess]

    def post(self, request, ledger_id):
        ledger = get_object_or_404(Ledger, pk=ledger_id)
        serializer = TagAssignmentSerializer(
            data=request.data, context={"retail": _retail(request)},
        )
        serializer.is_valid(raise_exception=True)
        CustomerTagAssignment.objects.get_or_create(
            tag_id=serializer.validated_data["tag_id"],
            ledger=ledger,
            defaults={"assigned_by": request.user},
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    def delete(self, request, ledger_id):
        serializer = TagAssignmentSerializer(
            data=request.data, context={"retail": _retail(request)},
        )
        serializer.is_valid(raise_exception=True)
        CustomerTagAssignment.objects.filter(
            tag_id=serializer.validated_data["tag_id"], ledger_id=ledger_id,
        ).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class SegmentViewSet(RetailBaseViewset):
    """
    CRUD for saved segments.

    RBAC works normally here (there is a real queryset and model), so this uses
    the standard `RetailBaseViewset` rather than the analytics permission —
    but with `fy_scoped = False`, since a segment describes a customer
    relationship rather than a fiscal year's worth of it.
    """

    serializer_class = SegmentSerializer
    queryset = Segment.objects.all()
    fy_scoped = False

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["retail"] = _retail(self.request)
        return context

    def perform_create(self, serializer):
        serializer.save(retail=_retail(self.request), created_by=self.request.user)

    @action(detail=False, methods=["post"])
    def preview(self, request):
        """
        Count and sample a definition without saving it — the live feedback
        the segment builder shows while you are still editing rules.
        """
        from customer_intel.services.segments import evaluate

        retail = _retail(request)
        try:
            members = evaluate(request.data.get("definition") or {}, retail)
        except DjangoValidationError as exc:
            return Response(
                {"error": exc.messages if hasattr(exc, "messages") else str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        sample = members[:25]
        return Response({
            "count": len(members),
            "sample": CustomerListSerializer(
                sample, many=True,
                context={"mask_customers": not can_user_view_customer_data(request.user)},
            ).data,
        })

    @action(detail=True, methods=["get"])
    def members(self, request, pk=None):
        from customer_intel.services.segments import evaluate

        segment = self.get_object()
        try:
            members = evaluate(segment, _retail(request))
        except DjangoValidationError as exc:
            return Response(
                {"error": exc.messages if hasattr(exc, "messages") else str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        segment.last_member_count = len(members)
        segment.last_evaluated_at = timezone.now()
        segment.save(update_fields=["last_member_count", "last_evaluated_at"])

        paginator = CustomPagination()
        page = paginator.paginate_queryset(members, request, view=self)
        return paginator.get_paginated_response(
            CustomerListSerializer(
                page, many=True,
                context={"mask_customers": not can_user_view_customer_data(request.user)},
            ).data
        )

    @action(detail=False, methods=["get"])
    def fields(self, request):
        """
        The catalogue of filterable fields.

        Served from the backend so the builder UI and the compiler can never
        disagree about what is filterable.
        """
        from customer_intel.services.segments import registry_json

        return Response(registry_json())

    @action(detail=True, methods=["get"], url_path="meta-audience",
            permission_classes=[CanExportCustomerData])
    def meta_audience(self, request, pk=None):
        """
        Download the segment as a Meta Custom Audience file.

        Every value is SHA-256 hashed before it leaves — Meta matches on its
        own side and nothing per-person comes back. Opted-out customers are
        excluded, and the export itself is recorded in AudienceExport because
        this is a cross-border transfer of pseudonymous personal data.
        """
        from django.http import HttpResponse

        from customer_intel.models import AudienceExport
        from customer_intel.services.audiences import SCHEMA, build_rows, write_csv
        from customer_intel.services.segments import evaluate

        segment = self.get_object()
        retail = _retail(request)
        members = evaluate(segment, retail)
        rows, stats = build_rows(members, retail)

        AudienceExport.objects.create(
            retail=retail, segment=segment, segment_name=segment.name, method="csv",
            row_count=stats["exported"],
            skipped_opted_out=stats["opted_out"],
            skipped_no_identifier=stats["no_identifier"],
            fields_exported=SCHEMA, exported_by=request.user,
        )

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = (
            f'attachment; filename="meta-audience-{segment.id}.csv"'
        )
        response["X-Audience-Total"] = str(stats["total"])
        response["X-Audience-Exported"] = str(stats["exported"])
        response["X-Audience-Opted-Out"] = str(stats["opted_out"])
        write_csv(response, rows)
        return response

    @action(detail=True, methods=["get"], url_path="export",
            permission_classes=[CanExportCustomerData])
    def export_csv(self, request, pk=None):
        """
        Download a segment as CSV.

        Behind its own permission: reading one customer's record while serving
        them is routine, downloading the whole book is not.
        """
        import csv

        from django.http import HttpResponse

        from customer_intel.services.segments import evaluate

        segment = self.get_object()
        members = evaluate(segment, _retail(request))

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = (
            f'attachment; filename="segment-{segment.id}-{segment.name[:40]}.csv"'
        )
        writer = csv.writer(response)
        writer.writerow([
            "Name", "Mobile", "Email", "City", "Lifetime value",
            "Purchases", "Last purchase", "Segment", "Lapse risk", "Confidence",
        ])
        for snapshot in members:
            ledger = snapshot.ledger
            writer.writerow([
                ledger.ac_name, ledger.mobile1 or "", ledger.email or "",
                ledger.city or "", snapshot.lifetime_value,
                snapshot.purchase_count_all, snapshot.last_purchase_date or "",
                snapshot.rfm_segment,
                # Same rule the UI follows: below 'medium' confidence there is
                # not enough history to call lapse risk, so the column stays
                # blank rather than exporting a verdict we cannot stand behind.
                snapshot.lapse_band if snapshot.cadence_is_meaningful else "",
                snapshot.confidence_reason or snapshot.confidence,
            ])
        return response


class CustomerTagViewSet(RetailBaseViewset):
    """CRUD for the retail's customer tags."""

    serializer_class = CustomerTagSerializer
    queryset = CustomerTag.objects.all()
    # Tags describe a customer relationship, not a fiscal year's worth of it.
    fy_scoped = False

    def get_queryset(self):
        return (
            super().get_queryset()
            .annotate(assigned_count=Count("assignments"))
            .order_by("name", "id")
        )


class MessageTemplateViewSet(RetailBaseViewset):
    """Reusable message bodies / provider template names."""

    serializer_class = MessageTemplateSerializer
    queryset = MessageTemplate.objects.all()
    fy_scoped = False

    def get_queryset(self):
        return super().get_queryset().order_by("name", "id")


class CampaignViewSet(RetailBaseViewset):
    """
    Campaign CRUD plus the launch controls.

    Sending is not done here — `launch` only flips the campaign to running and
    materialises its recipients. The actual sends are drip-fed by the per-minute
    `run_due_campaigns` command so provider rate limits are respected and a
    campaign can be paused mid-flight.
    """

    serializer_class = CampaignSerializer
    queryset = Campaign.objects.all()
    fy_scoped = False

    def get_queryset(self):
        return (
            super().get_queryset()
            .select_related("segment", "template", "created_by")
            .order_by("-created_at", "-id")
        )

    def perform_create(self, serializer):
        serializer.save(retail=_retail(self.request), created_by=self.request.user)

    @action(detail=True, methods=["post"])
    def preview(self, request, pk=None):
        """How many will actually receive this, and what will it say."""
        from customer_intel.services.campaigns import render_message
        from customer_intel.services.segments import evaluate

        campaign = self.get_object()
        members = evaluate(campaign.segment, _retail(request))

        opted_out = CustomerSocialProfile.objects.filter(
            ledger_id__in=[m.ledger_id for m in members],
        ).filter(Q(opt_out_at__isnull=False) | Q(whatsapp_opt_in=False)).count()

        body = campaign.message_body or (
            campaign.template.body if campaign.template_id else ""
        )
        sample_text = (
            render_message(body, members[0].ledger, campaign.retail)
            if members else render_message(body, request.user, campaign.retail)
        )
        return Response({
            "total": len(members),
            "opted_out": opted_out,
            "sendable": max(0, len(members) - opted_out),
            "sample_message": sample_text,
        })

    @action(detail=True, methods=["post"])
    def launch(self, request, pk=None):
        """
        Materialise recipients and start (or schedule) the campaign.

        Refuses to relaunch anything already past draft/scheduled — the whole
        point of the recipient table is that a campaign is sent once.
        """
        from django.db import transaction

        from accounting.utils import get_next_bill_number
        from customer_intel.services.campaigns import materialise

        campaign = self.get_object()
        if campaign.status not in ("draft", "scheduled"):
            return Response(
                {"error": f"This campaign is already {campaign.status}."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            if not campaign.campaign_no:
                try:
                    campaign.campaign_no = get_next_bill_number(
                        _retail(request), "CMP",
                    )
                except ValueError as exc:
                    return Response({"error": str(exc)},
                                    status=status.HTTP_400_BAD_REQUEST)

            counts = materialise(campaign)

            scheduled = campaign.scheduled_at and campaign.scheduled_at > timezone.now()
            campaign.status = "scheduled" if scheduled else "running"
            if not scheduled:
                campaign.started_at = timezone.now()
            campaign.save(update_fields=[
                "campaign_no", "status", "started_at",
            ])

        return Response({"status": campaign.status, "campaign_no": campaign.campaign_no,
                         **counts})

    @action(detail=True, methods=["post"])
    def pause(self, request, pk=None):
        campaign = self.get_object()
        if campaign.status != "running":
            return Response({"error": "Only a running campaign can be paused."},
                            status=status.HTTP_400_BAD_REQUEST)
        campaign.status = "paused"
        campaign.save(update_fields=["status"])
        return Response({"status": campaign.status})

    @action(detail=True, methods=["post"])
    def resume(self, request, pk=None):
        campaign = self.get_object()
        if campaign.status != "paused":
            return Response({"error": "Only a paused campaign can be resumed."},
                            status=status.HTTP_400_BAD_REQUEST)
        campaign.status = "running"
        campaign.save(update_fields=["status"])
        return Response({"status": campaign.status})

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        """Stop a campaign and drop anything not yet sent."""
        campaign = self.get_object()
        if campaign.status in ("completed", "cancelled"):
            return Response({"error": f"Already {campaign.status}."},
                            status=status.HTTP_400_BAD_REQUEST)
        campaign.recipients.filter(status__in=["pending", "queued"]).update(
            status="skipped", error_message="Campaign cancelled",
        )
        campaign.status = "cancelled"
        campaign.finished_at = timezone.now()
        campaign.save(update_fields=["status", "finished_at"])
        return Response({"status": campaign.status})

    @action(detail=True, methods=["get"])
    def recipients(self, request, pk=None):
        campaign = self.get_object()
        qs = campaign.recipients.select_related("ledger").order_by("id")
        state = request.query_params.get("status")
        if state:
            qs = qs.filter(status__in=[s for s in state.split(",") if s])

        paginator = CustomPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        return paginator.get_paginated_response(
            CampaignRecipientSerializer(page, many=True).data
        )


class WorklistView(APIView):
    """
    GET /customer-intel/api/worklist/

    Today's call list. Computed on read so an order that turned "ready" a
    moment ago appears immediately; RFM and cadence come from the snapshot.
    """

    permission_classes = [HasIntelAccess]

    def get(self, request):
        from customer_intel.services.worklist import build_worklist

        retail = _retail(request)
        if retail is None:
            return Response({"error": "No active retail on the request."},
                            status=status.HTTP_400_BAD_REQUEST)

        try:
            limit = min(500, int(request.query_params.get("limit", 100)))
        except ValueError:
            limit = 100

        rows = build_worklist(
            retail, limit=limit,
            include_contacted=request.query_params.get("include_contacted") == "true",
        )

        reason = request.query_params.get("reason")
        if reason:
            wanted = {r for r in reason.split(",") if r}
            rows = [r for r in rows if r["reason_code"] in wanted]

        if not can_user_view_customer_data(request.user):
            for row in rows:
                row["ac_name"] = "****"
                row["mobile"] = "****"

        return Response({"count": len(rows), "results": rows})
