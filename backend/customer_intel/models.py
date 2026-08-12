"""
Customer 360 — profiling, engagement timeline and consent.

RETAIL SCOPING RULE (applies to every query in this app):
    A Ledger belongs to a retail's customer base if EITHER
      * `Ledger.retail_code_id == retail_id`, OR
      * the ledger has at least one `SalesVou` in that retail.
    Sales are authoritative — a customer registered at branch A who buys at
    branch B is a customer of branch B too. Note this deliberately differs from
    `contacts.crm_sender.find_due_recipients`, which scopes on `retail_code`
    alone, so customer counts here will not match the CRM occasions page.

CONFIDENCE:
    Frequency / cadence / lapse metrics are only meaningful with multiple
    purchases spread over time. Every snapshot carries `confidence` and
    `confidence_reason`; the UI must suppress cadence and lapse output when
    confidence is 'none' or 'low' rather than presenting a made-up number.
"""

from django.db import models


# ── choice constants ──────────────────────────────────────────────────────────

RFM_SEGMENTS = [
    ("champion", "Champion"),
    ("loyal", "Loyal"),
    ("cant_lose", "Can't Lose"),
    ("at_risk", "At Risk"),
    ("hibernating", "Hibernating"),
    ("lost", "Lost"),
    ("new", "New"),
    ("promising", "Promising"),
    ("potential_loyalist", "Potential Loyalist"),
    ("needs_attention", "Needs Attention"),
    ("about_to_sleep", "About to Sleep"),
]

LAPSE_BANDS = [
    ("healthy", "Healthy"),
    ("due", "Due"),
    ("at_risk", "At Risk"),
    ("lapsed", "Lapsed"),
    ("never", "Never Purchased"),
]

CONFIDENCE_LEVELS = [
    ("none", "No purchase history"),
    ("low", "Low"),
    ("medium", "Medium"),
    ("high", "High"),
]

GAP_BASIS = [
    ("own", "Own purchase gaps"),
    ("blended", "Blended with cohort"),
    ("cohort", "Cohort median"),
    ("none", "Not computable"),
]

SCORING_BASIS = [
    ("quintile", "Quintiles of active cohort"),
    ("absolute", "Absolute bands"),
]


class CustomerProfileSnapshot(models.Model):
    """
    Denormalised per-customer analytics, rebuilt nightly by
    `manage.py rebuild_customer_profiles`.

    Deliberately NOT fiscal-year scoped — lifetime value and buying cadence are
    meaningless inside a single FY. Any ViewSet exposing this must therefore set
    `fy_scoped = False` (see userauth.views.RetailBaseViewset).
    """

    retail = models.ForeignKey(
        "mastersconfig.RetailMaster", on_delete=models.CASCADE,
        related_name="customer_snapshots",
    )
    ledger = models.ForeignKey(
        "contacts.Ledger", on_delete=models.CASCADE, related_name="intel_snapshots",
    )

    # ── recency / frequency / monetary ────────────────────────────────────────
    first_purchase_date = models.DateField(null=True, blank=True)
    last_purchase_date = models.DateField(null=True, blank=True, db_index=True)
    days_since_last = models.IntegerField(null=True, blank=True, db_index=True)
    purchase_count = models.IntegerField(default=0)       # within the scoring window
    purchase_count_all = models.IntegerField(default=0)   # lifetime
    gross_spend = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    returns_value = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    net_spend = models.DecimalField(max_digits=20, decimal_places=2, default=0, db_index=True)
    lifetime_value = models.DecimalField(max_digits=20, decimal_places=2, default=0)

    r_score = models.SmallIntegerField(null=True, blank=True)
    f_score = models.SmallIntegerField(null=True, blank=True)
    m_score = models.SmallIntegerField(null=True, blank=True)
    rfm_cell = models.CharField(max_length=3, blank=True)
    rfm_segment = models.CharField(max_length=24, blank=True, db_index=True, choices=RFM_SEGMENTS)
    scoring_basis = models.CharField(max_length=12, blank=True, choices=SCORING_BASIS)

    # ── how much to trust the derived metrics ─────────────────────────────────
    confidence = models.CharField(
        max_length=8, default="none", choices=CONFIDENCE_LEVELS, db_index=True,
    )
    confidence_reason = models.CharField(max_length=120, blank=True)

    # ── cadence / lapse ───────────────────────────────────────────────────────
    median_gap_days = models.IntegerField(null=True, blank=True)
    mean_gap_days = models.IntegerField(null=True, blank=True)
    gap_basis = models.CharField(max_length=8, blank=True, choices=GAP_BASIS)
    next_expected_date = models.DateField(null=True, blank=True, db_index=True)
    lapse_ratio = models.DecimalField(max_digits=8, decimal_places=3, null=True, blank=True)
    lapse_band = models.CharField(max_length=12, blank=True, db_index=True, choices=LAPSE_BANDS)

    # ── ticket size ───────────────────────────────────────────────────────────
    avg_ticket = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    median_ticket = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    min_ticket = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    max_ticket = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    p25_ticket = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    p75_ticket = models.DecimalField(max_digits=18, decimal_places=2, default=0)

    # ── preference vectors ────────────────────────────────────────────────────
    # Each list holds up to 10 dicts: {id, label, amount, pcs, gw, share}
    category_prefs = models.JSONField(default=list, blank=True)
    purity_prefs = models.JSONField(default=list, blank=True)
    metal_color_prefs = models.JSONField(default=list, blank=True)
    design_prefs = models.JSONField(default=list, blank=True)
    # {shape: [...], clarity: [...], color: [...], cut: [...], solitaire: {...}}
    stone_prefs = models.JSONField(default=dict, blank=True)
    top_category_id = models.IntegerField(null=True, blank=True, db_index=True)
    top_purity_id = models.IntegerField(null=True, blank=True, db_index=True)

    # ── engagement rollup ─────────────────────────────────────────────────────
    last_contacted_at = models.DateTimeField(null=True, blank=True)
    last_inbound_at = models.DateTimeField(null=True, blank=True)
    catalog_views_90d = models.IntegerField(default=0)
    engagement_score = models.SmallIntegerField(default=0)
    engagement_components = models.JSONField(default=dict, blank=True)

    # Copied from Ledger so B2B can later be scored in its own cohort without a
    # schema change or a full rebuild.
    b2b = models.BooleanField(default=False, db_index=True)

    computed_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "customer_profile_snapshot"
        constraints = [
            models.UniqueConstraint(
                fields=["retail", "ledger"], name="uniq_cps_retail_ledger",
            ),
        ]
        indexes = [
            models.Index(fields=["retail", "-net_spend"], name="idx_cps_retail_spend"),
            models.Index(fields=["retail", "-last_purchase_date"], name="idx_cps_retail_lastpur"),
            models.Index(fields=["retail", "rfm_segment"], name="idx_cps_retail_seg"),
            models.Index(fields=["retail", "lapse_band"], name="idx_cps_retail_lapse"),
            models.Index(fields=["retail", "next_expected_date"], name="idx_cps_retail_nextexp"),
        ]

    def __str__(self):
        return f"{self.ledger_id} @ {self.retail_id} ({self.rfm_segment or 'unscored'})"

    @property
    def cadence_is_meaningful(self):
        """Cadence and lapse output should be hidden below 'medium' confidence."""
        return self.confidence in ("medium", "high")


class MessageTemplate(models.Model):
    """
    A message the retailer can send.

    `provider_template_name` matters more than `body` for WhatsApp: Meta will
    not deliver arbitrary text outside a 24-hour customer-service window, so a
    campaign must name a template that has already been approved on the
    provider side. `body` is used by free-form providers (the generic webhook)
    and to render the preview shown in the UI.
    """

    retail = models.ForeignKey(
        "mastersconfig.RetailMaster", on_delete=models.CASCADE,
        related_name="message_templates",
    )
    name = models.CharField(max_length=100)
    channel = models.CharField(max_length=16, default="whatsapp")
    provider_template_name = models.CharField(max_length=100, blank=True)
    body = models.TextField(blank=True)
    # Ordered placeholder names, e.g. ["customer_name", "offer_pct"].
    variables = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "crm_message_template"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["retail", "name"], name="uniq_msgtpl"),
        ]

    def __str__(self):
        return self.name


class Campaign(models.Model):
    """
    One send of one message to one segment.

    Sending is drip-fed rather than fired in a single burst — see
    customer_intel.services.campaigns. Provider rate limits and the
    django-tasks backend (which has no native rate limiter) both make a
    self-rescheduling slice the right shape.
    """

    STATUS = [
        ("draft", "Draft"),
        ("scheduled", "Scheduled"),
        ("running", "Running"),
        ("paused", "Paused"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
        ("failed", "Failed"),
    ]

    retail = models.ForeignKey(
        "mastersconfig.RetailMaster", on_delete=models.CASCADE,
        related_name="campaigns",
    )
    name = models.CharField(max_length=120)
    campaign_no = models.CharField(max_length=30, blank=True)
    channel = models.CharField(max_length=16, default="whatsapp")
    # String reference: Segment is declared further down this module.
    segment = models.ForeignKey(
        "customer_intel.Segment", on_delete=models.PROTECT, related_name="campaigns",
    )
    template = models.ForeignKey(
        MessageTemplate, on_delete=models.PROTECT, null=True, blank=True,
        related_name="campaigns",
    )
    message_body = models.TextField(blank=True)

    catalog_share = models.ForeignKey(
        "inventory.CatalogShare", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="campaigns",
    )
    attach_catalog_link = models.BooleanField(default=False)
    per_recipient_share = models.BooleanField(
        default=False,
        help_text="Mint a per-customer catalog link so opens are attributable.",
    )

    scheduled_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=12, choices=STATUS, default="draft", db_index=True)
    throttle_per_minute = models.PositiveIntegerField(default=20)

    total_recipients = models.IntegerField(default=0)
    sent_count = models.IntegerField(default=0)
    failed_count = models.IntegerField(default=0)
    skipped_count = models.IntegerField(default=0)

    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    last_error = models.CharField(max_length=500, blank=True)
    created_by = models.ForeignKey(
        "auth.User", on_delete=models.SET_NULL, null=True, blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "crm_campaign"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["retail", "campaign_no"], name="uniq_campaign_no",
            ),
        ]

    def __str__(self):
        return f"{self.campaign_no or 'DRAFT'} — {self.name}"

    @property
    def pending_count(self):
        return self.recipients.filter(status="pending").count()


class CampaignRecipient(models.Model):
    """
    One customer's place in one campaign.

    This is also the record of who was actually contacted, which is why
    segments do not need a frozen membership table — the segment answers
    "who matches now", this answers "who did we send to".
    """

    STATUS = [
        ("pending", "Pending"),
        ("queued", "Queued"),
        ("sent", "Sent"),
        ("delivered", "Delivered"),
        ("read", "Read"),
        ("replied", "Replied"),
        ("failed", "Failed"),
        ("skipped", "Skipped"),
        ("opted_out", "Opted Out"),
    ]

    campaign = models.ForeignKey(
        Campaign, on_delete=models.CASCADE, related_name="recipients",
    )
    ledger = models.ForeignKey(
        "contacts.Ledger", on_delete=models.PROTECT, related_name="campaign_receipts",
    )
    mobile = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    rendered_message = models.TextField(blank=True)
    catalog_share = models.ForeignKey(
        "inventory.CatalogShare", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="campaign_recipients",
    )
    status = models.CharField(max_length=12, choices=STATUS, default="pending", db_index=True)
    provider_msg_id = models.CharField(max_length=120, blank=True, db_index=True)
    error_message = models.CharField(max_length=500, blank=True)
    queued_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)

    class Meta:
        db_table = "crm_campaign_recipient"
        constraints = [
            models.UniqueConstraint(
                fields=["campaign", "ledger"], name="uniq_camp_recipient",
            ),
        ]
        indexes = [models.Index(fields=["campaign", "status"], name="idx_campres_status")]


class InboundWebhookLog(models.Model):
    """
    Raw inbound provider payloads, stored before parsing.

    The webhook endpoint verifies the signature, persists here, enqueues, and
    returns 200 immediately — Meta retries aggressively on any non-200 and
    would otherwise duplicate the timeline.
    """

    retail = models.ForeignKey(
        "mastersconfig.RetailMaster", on_delete=models.CASCADE,
        related_name="inbound_webhooks",
    )
    provider = models.CharField(max_length=20, blank=True)
    payload = models.JSONField(default=dict)
    processed = models.BooleanField(default=False, db_index=True)
    error_message = models.CharField(max_length=500, blank=True)
    received_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "crm_inbound_webhook_log"
        ordering = ["-received_at"]


class AudienceExport(models.Model):
    """
    A record that customer identifiers left the building.

    Hashing makes a Meta audience file pseudonymous, not anonymous — matching
    is the entire purpose. Under the DPDP Act that makes an export a
    cross-border transfer of personal data, so who exported what, when, and
    which fields were included is worth keeping. This row is the record.
    """

    METHOD = [("csv", "CSV download"), ("api", "Meta Marketing API")]

    retail = models.ForeignKey(
        "mastersconfig.RetailMaster", on_delete=models.CASCADE,
        related_name="audience_exports",
    )
    # SET_NULL, not PROTECT: the audit record must outlive the segment. Making
    # it PROTECT would mean that exporting a segment once permanently prevents
    # deleting it, which is a worse outcome than an orphaned audit row — hence
    # `segment_name` keeps the record readable after the segment is gone.
    segment = models.ForeignKey(
        "customer_intel.Segment", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="audience_exports",
    )
    segment_name = models.CharField(max_length=100, blank=True)
    method = models.CharField(max_length=10, choices=METHOD, default="csv")
    row_count = models.IntegerField(default=0)
    skipped_opted_out = models.IntegerField(default=0)
    skipped_no_identifier = models.IntegerField(default=0)
    fields_exported = models.JSONField(default=list, blank=True)
    meta_audience_id = models.CharField(max_length=40, blank=True)
    status = models.CharField(max_length=12, default="completed")
    error_message = models.CharField(max_length=500, blank=True)
    exported_by = models.ForeignKey(
        "auth.User", on_delete=models.SET_NULL, null=True, blank=True,
    )
    exported_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "crm_audience_export"
        ordering = ["-exported_at"]


class CatalogViewEvent(models.Model):
    """
    Someone looked at a shared catalog.

    This is the only genuine intent signal the system gets between purchases:
    it says which designs a named customer lingered on, before they walk in.

    Privacy: the visitor's IP is stored only as a salted hash. A raw IP would
    be personal data under the DPDP Act for no analytical gain — the hash is
    enough to tell two sessions apart.
    """

    KIND = [
        ("open", "Opened the catalog"),
        ("page", "Viewed a page"),
        ("design", "Viewed a design"),
        ("pdf", "Downloaded the PDF"),
        ("enquiry", "Made an enquiry"),
    ]

    share = models.ForeignKey(
        "inventory.CatalogShare", on_delete=models.CASCADE, related_name="view_events",
    )
    ledger = models.ForeignKey(
        "contacts.Ledger", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="catalog_view_events",
    )
    retail = models.ForeignKey(
        "mastersconfig.RetailMaster", on_delete=models.CASCADE,
        related_name="catalog_view_events",
    )
    kind = models.CharField(max_length=16, choices=KIND, db_index=True)
    design = models.ForeignKey(
        "inventory.DesignMain", on_delete=models.SET_NULL, null=True, blank=True,
    )
    page = models.IntegerField(null=True, blank=True)
    session_key = models.CharField(max_length=40, blank=True, db_index=True)
    ip_hash = models.CharField(max_length=64, blank=True)
    user_agent = models.CharField(max_length=300, blank=True)
    occurred_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "catalog_view_event"
        ordering = ["-occurred_at"]
        indexes = [
            models.Index(fields=["retail", "ledger", "-occurred_at"], name="idx_cve_ldgr_time"),
            models.Index(fields=["share", "kind"], name="idx_cve_share_kind"),
        ]


class CustomerDataExport(CustomerProfileSnapshot):
    """
    Permission anchor only — no table of its own.

    Exists so that "may bulk-export customer PII" is a separately grantable
    capability in the role editor, distinct from "may view a customer profile".
    See customer_intel.permissions.CanExportCustomerData.
    """

    class Meta:
        proxy = True
        verbose_name = "Customer data export"
        verbose_name_plural = "Customer data exports"


class EngagementEvent(models.Model):
    """
    Append-only unified customer communication + intent timeline.

    `ledger` is a real FK here, unlike the legacy `mastersconfig.CRMSendLog`
    which stores a bare integer — the timeline needs joins.
    """

    CHANNEL = [
        ("whatsapp", "WhatsApp"),
        ("email", "Email"),
        ("sms", "SMS"),
        ("call", "Phone Call"),
        ("walk_in", "Walk-in"),
        ("catalog", "Catalog"),
        ("portal", "Customer Portal"),
        ("note", "Internal Note"),
    ]
    DIRECTION = [("out", "Outbound"), ("in", "Inbound"), ("sys", "System")]
    STATUS = [
        ("queued", "Queued"),
        ("sent", "Sent"),
        ("delivered", "Delivered"),
        ("read", "Read"),
        ("failed", "Failed"),
        ("skipped", "Skipped"),
        ("received", "Received"),
    ]

    retail = models.ForeignKey(
        "mastersconfig.RetailMaster", on_delete=models.CASCADE,
        related_name="engagement_events",
    )
    ledger = models.ForeignKey(
        "contacts.Ledger", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="engagement_events",
    )
    channel = models.CharField(max_length=16, choices=CHANNEL, db_index=True)
    direction = models.CharField(max_length=4, choices=DIRECTION, default="out")
    # occasion_birthday | occasion_anniversary | campaign | catalog_open |
    # catalog_design_view | inbound_reply | manual_note | scheme_reminder | order_ready
    event_type = models.CharField(max_length=32, db_index=True)
    subject = models.CharField(max_length=200, blank=True)
    body = models.TextField(blank=True)
    status = models.CharField(max_length=12, choices=STATUS, default="sent")
    error_message = models.CharField(max_length=500, blank=True)

    to_address = models.CharField(max_length=120, blank=True)
    provider = models.CharField(max_length=20, blank=True)
    # Correlates delivery receipts and inbound replies back to the outbound send.
    provider_msg_id = models.CharField(max_length=120, blank=True, db_index=True)

    campaign = models.ForeignKey(
        "customer_intel.Campaign", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="events",
    )
    catalog_share = models.ForeignKey(
        "inventory.CatalogShare", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="engagement_events",
    )
    design = models.ForeignKey(
        "inventory.DesignMain", on_delete=models.SET_NULL, null=True, blank=True,
    )

    metadata = models.JSONField(default=dict, blank=True)
    occurred_at = models.DateTimeField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        "auth.User", on_delete=models.SET_NULL, null=True, blank=True,
    )

    class Meta:
        db_table = "engagement_event"
        ordering = ["-occurred_at"]
        indexes = [
            models.Index(fields=["retail", "ledger", "-occurred_at"], name="idx_ee_retail_ldgr_time"),
            models.Index(fields=["retail", "-occurred_at"], name="idx_ee_retail_time"),
            models.Index(fields=["retail", "channel", "direction"], name="idx_ee_chan_dir"),
        ]

    def __str__(self):
        return f"{self.channel}/{self.event_type} → {self.ledger_id} @ {self.occurred_at:%Y-%m-%d}"


class CustomerTag(models.Model):
    """Retail-scoped label applied to customers, manually or by the nightly job."""

    retail = models.ForeignKey(
        "mastersconfig.RetailMaster", on_delete=models.CASCADE,
        related_name="customer_tags",
    )
    name = models.CharField(max_length=50)
    slug = models.SlugField(max_length=60)
    color = models.CharField(max_length=20, blank=True, default="slate")
    description = models.CharField(max_length=200, blank=True)
    is_system = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "customer_tag"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["retail", "slug"], name="uniq_tag_retail_slug"),
        ]

    def __str__(self):
        return self.name


class CustomerTagAssignment(models.Model):
    tag = models.ForeignKey(CustomerTag, on_delete=models.CASCADE, related_name="assignments")
    ledger = models.ForeignKey(
        "contacts.Ledger", on_delete=models.CASCADE, related_name="intel_tags",
    )
    assigned_at = models.DateTimeField(auto_now_add=True)
    assigned_by = models.ForeignKey(
        "auth.User", on_delete=models.SET_NULL, null=True, blank=True,
    )

    class Meta:
        db_table = "customer_tag_assignment"
        constraints = [
            models.UniqueConstraint(fields=["tag", "ledger"], name="uniq_tagassign"),
        ]
        indexes = [models.Index(fields=["ledger"], name="idx_tagassign_ledger")]


class Segment(models.Model):
    """
    A saved, named customer filter — the unit campaigns and audience exports
    are aimed at.

    `definition` is a validated rule list, not free-form ORM lookups. It is
    compiled by customer_intel.services.segments.SegmentCompiler against a
    whitelist; anything outside the registry is rejected. See that module for
    why (this JSON reaches the database).

    Membership is evaluated live rather than cached — a segment is a question,
    not a snapshot. Reproducibility of "who did we actually send to" comes from
    CampaignRecipient instead.
    """

    retail = models.ForeignKey(
        "mastersconfig.RetailMaster", on_delete=models.CASCADE,
        related_name="segments",
    )
    name = models.CharField(max_length=100)
    description = models.CharField(max_length=300, blank=True)
    definition = models.JSONField(default=dict)
    is_active = models.BooleanField(default=True)
    last_evaluated_at = models.DateTimeField(null=True, blank=True)
    last_member_count = models.IntegerField(default=0)
    created_by = models.ForeignKey(
        "auth.User", on_delete=models.SET_NULL, null=True, blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "customer_segment"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["retail", "name"], name="uniq_segment_retail_name",
            ),
        ]

    def __str__(self):
        return self.name


class CustomerSocialProfile(models.Model):
    """
    Marketing / consent attributes for a customer.

    Deliberately a separate OneToOne rather than columns on `ledger_master`:
    Ledger is the shared party master for karigars, vendors, banks and system
    ledgers, so customer-marketing columns there would be null for most rows.
    Follows the `contacts.BankAccountProfile` precedent.

    Consent model (per the retailer's decision): marketing is opt-out, not
    opt-in — `whatsapp_opt_in` / `email_opt_in` default True. `opt_out_at` is
    absolute and must be honoured by EVERY send path and EVERY audience export.
    """

    GENDER = [("M", "Male"), ("F", "Female"), ("O", "Other")]

    ledger = models.OneToOneField(
        "contacts.Ledger", on_delete=models.CASCADE, related_name="social_profile",
    )
    gender = models.CharField(max_length=1, choices=GENDER, blank=True)
    instagram = models.CharField(max_length=80, blank=True)
    facebook = models.CharField(max_length=120, blank=True)

    whatsapp_opt_in = models.BooleanField(default=True)
    email_opt_in = models.BooleanField(default=True)
    opt_out_at = models.DateTimeField(null=True, blank=True)
    opt_out_reason = models.CharField(max_length=200, blank=True)
    consent_source = models.CharField(max_length=60, blank=True)
    consent_at = models.DateTimeField(null=True, blank=True)

    preferred_language = models.CharField(max_length=10, blank=True, default="en")
    notes = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "customer_social_profile"

    def __str__(self):
        return f"social profile for ledger {self.ledger_id}"

    @property
    def is_marketable_whatsapp(self):
        return self.whatsapp_opt_in and self.opt_out_at is None

    @property
    def is_marketable_email(self):
        return self.email_opt_in and self.opt_out_at is None
