"""Serializers for the Customer 360 API."""

from django.utils.text import slugify
from rest_framework import serializers

from contacts.masking import mask_ledger_representation
from customer_intel.models import (
    CustomerProfileSnapshot,
    CustomerSocialProfile,
    CustomerTag,
    CustomerTagAssignment,
    EngagementEvent,
    Campaign,
    CampaignRecipient,
    MessageTemplate,
    Segment,
)


class CustomerTagSerializer(serializers.ModelSerializer):
    assigned_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = CustomerTag
        fields = [
            "id", "name", "slug", "color", "description", "is_system",
            "created_at", "assigned_count",
        ]
        read_only_fields = ["slug", "is_system", "created_at"]

    def create(self, validated_data):
        validated_data["slug"] = slugify(validated_data["name"])[:60]
        return super().create(validated_data)

    def update(self, instance, validated_data):
        if "name" in validated_data:
            validated_data["slug"] = slugify(validated_data["name"])[:60]
        return super().update(instance, validated_data)


class CustomerSocialProfileSerializer(serializers.ModelSerializer):
    """
    Marketing attributes and consent.

    `opt_out_at` is read-only here — opting out happens through the dedicated
    action (or an inbound STOP message), so that it always writes an audit trail
    rather than being silently toggled by a form PATCH.
    """

    class Meta:
        model = CustomerSocialProfile
        fields = [
            "gender", "instagram", "facebook",
            "whatsapp_opt_in", "email_opt_in",
            "opt_out_at", "opt_out_reason",
            "consent_source", "consent_at",
            "preferred_language", "notes", "updated_at",
        ]
        read_only_fields = ["opt_out_at", "opt_out_reason", "updated_at"]


class EngagementEventSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(
        source="created_by.username", read_only=True, default="",
    )

    class Meta:
        model = EngagementEvent
        fields = [
            "id", "channel", "direction", "event_type", "subject", "body",
            "status", "error_message", "to_address", "provider",
            "occurred_at", "created_at", "created_by_name", "metadata",
        ]


class CustomerListSerializer(serializers.ModelSerializer):
    """
    A row in the customer list.

    Identity fields are pulled off the related Ledger and run through the same
    masking rules the ledger API uses, so a user without the unmasked-customer
    permission does not get the customer book by way of this endpoint.
    """

    ledger_id = serializers.IntegerField(source="ledger.id", read_only=True)
    ac_name = serializers.CharField(source="ledger.ac_name", read_only=True)
    mobile1 = serializers.CharField(source="ledger.mobile1", read_only=True)
    email = serializers.CharField(source="ledger.email", read_only=True)
    city = serializers.CharField(source="ledger.city", read_only=True)
    dob = serializers.DateField(source="ledger.dob", read_only=True)
    anniversary = serializers.DateField(source="ledger.anniversary", read_only=True)
    tags = serializers.SerializerMethodField()

    class Meta:
        model = CustomerProfileSnapshot
        fields = [
            "id", "ledger_id", "ac_name", "mobile1", "email", "city",
            "dob", "anniversary",
            "purchase_count_all", "last_purchase_date", "days_since_last",
            "net_spend", "lifetime_value", "avg_ticket",
            "r_score", "f_score", "m_score", "rfm_cell", "rfm_segment",
            "confidence", "confidence_reason", "scoring_basis",
            "lapse_band", "next_expected_date",
            "engagement_score", "b2b", "top_category_id", "tags",
            "computed_at",
        ]

    def get_tags(self, obj):
        assignments = getattr(obj, "_prefetched_tags", None)
        if assignments is None:
            return []
        return [{"id": a.tag_id, "name": a.tag.name, "color": a.tag.color}
                for a in assignments]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if self.context.get("mask_customers"):
            # mask_ledger_representation works on the Ledger's own field names,
            # which is exactly what the flattened identity fields above use.
            data = mask_ledger_representation(data, instance.ledger)
        return data


class SegmentSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(
        source="created_by.username", read_only=True, default="",
    )

    class Meta:
        model = Segment
        fields = [
            "id", "name", "description", "definition", "is_active",
            "last_evaluated_at", "last_member_count",
            "created_by_name", "created_at", "updated_at",
        ]
        read_only_fields = [
            "last_evaluated_at", "last_member_count", "created_at", "updated_at",
        ]

    def validate_definition(self, value):
        """
        Compile the definition before saving it.

        A segment that cannot compile is worse than useless — it would fail at
        campaign-send time, after recipients had been promised.
        """
        from django.core.exceptions import ValidationError as DjangoValidationError

        from customer_intel.services.segments import SegmentCompiler

        retail = self.context.get("retail")
        try:
            SegmentCompiler(retail, value).queryset()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(
                exc.messages if hasattr(exc, "messages") else str(exc)
            )
        return value


class CustomerNoteSerializer(serializers.Serializer):
    """Free-text note logged against a customer's timeline."""

    body = serializers.CharField(max_length=4000)
    subject = serializers.CharField(max_length=200, required=False, allow_blank=True)
    channel = serializers.ChoiceField(
        choices=[c[0] for c in EngagementEvent.CHANNEL], default="note",
    )


class TagAssignmentSerializer(serializers.Serializer):
    tag_id = serializers.IntegerField()

    def validate_tag_id(self, value):
        retail = self.context["retail"]
        if not CustomerTag.objects.filter(id=value, retail=retail).exists():
            raise serializers.ValidationError("Unknown tag for this retail.")
        return value


class MessageTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = MessageTemplate
        fields = [
            "id", "name", "channel", "provider_template_name", "body",
            "variables", "is_active", "created_at",
        ]


class CampaignRecipientSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="ledger.ac_name", read_only=True)
    ledger_id = serializers.IntegerField(source="ledger.id", read_only=True)

    class Meta:
        model = CampaignRecipient
        fields = [
            "id", "ledger_id", "customer_name", "mobile", "status",
            "error_message", "sent_at", "attempts", "rendered_message",
        ]


class CampaignSerializer(serializers.ModelSerializer):
    segment_name = serializers.CharField(source="segment.name", read_only=True)
    template_name = serializers.CharField(
        source="template.name", read_only=True, default="",
    )
    created_by_name = serializers.CharField(
        source="created_by.username", read_only=True, default="",
    )
    pending_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Campaign
        fields = [
            "id", "name", "campaign_no", "channel", "segment", "segment_name",
            "template", "template_name", "message_body",
            "catalog_share", "attach_catalog_link", "per_recipient_share",
            "scheduled_at", "status", "throttle_per_minute",
            "total_recipients", "sent_count", "failed_count", "skipped_count",
            "pending_count", "started_at", "finished_at", "last_error",
            "created_by_name", "created_at",
        ]
        read_only_fields = [
            "campaign_no", "status", "total_recipients", "sent_count",
            "failed_count", "skipped_count", "started_at", "finished_at",
            "last_error", "created_at",
        ]

    def validate(self, attrs):
        """
        A WhatsApp campaign must name a provider-approved template.

        Meta will not deliver free-form text outside a 24-hour customer-service
        window; without this check a user would build a campaign that silently
        fails at send time with a 132000-series error.
        """
        channel = attrs.get("channel", getattr(self.instance, "channel", "whatsapp"))
        template = attrs.get("template", getattr(self.instance, "template", None))
        body = attrs.get("message_body", getattr(self.instance, "message_body", ""))

        if channel == "whatsapp" and template is None and not body:
            raise serializers.ValidationError({
                "template": "Choose an approved message template, or write a "
                            "message body for providers that accept free text.",
            })
        return attrs
