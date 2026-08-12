"""
Compile a saved segment definition into a queryset.

SECURITY: a segment definition is user-supplied JSON that turns into database
filters. Every field name and operator is checked against FIELD_REGISTRY below
and anything unrecognised raises ValidationError. Never build `Q()` from a
caller-supplied lookup string — that is how a filter builder becomes a data
exfiltration primitive (`ledger__portal_accounts__password_hash__startswith`
would otherwise be a legal "field").

The registry is also served to the frontend via GET /api/segments/fields/, so
the backend stays the single source of truth for what is filterable.
"""

from datetime import date

from django.core.exceptions import ValidationError
from django.db.models import Q

from contacts.crm_utils import days_until_this_year
from customer_intel.models import CustomerProfileSnapshot

# op name -> ORM lookup suffix. 'eq' maps to exact.
OPS = {
    "eq": "",
    "ne": "",           # handled by negation
    "in": "__in",
    "gt": "__gt",
    "gte": "__gte",
    "lt": "__lt",
    "lte": "__lte",
    "icontains": "__icontains",
    "iexact": "__iexact",
    "isnull": "__isnull",
}

NUMERIC_OPS = ["eq", "ne", "gt", "gte", "lt", "lte"]
CHOICE_OPS = ["eq", "ne", "in"]
TEXT_OPS = ["eq", "iexact", "icontains"]
BOOL_OPS = ["eq"]


def _num(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        raise ValidationError(f"'{value}' is not a number.")


def _int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ValidationError(f"'{value}' is not a whole number.")


def _bool(value):
    if isinstance(value, bool):
        return value
    return str(value).lower() in ("1", "true", "yes")


def _str(value):
    return str(value)


def _list(coerce):
    def inner(value):
        if not isinstance(value, (list, tuple)):
            raise ValidationError("This operator needs a list of values.")
        return [coerce(v) for v in value]
    return inner


class Field:
    """One filterable attribute: where it lives, what you may ask of it."""

    def __init__(self, key, path, ops, coerce, label, group, kind="number",
                 choices=None, post=False, presence=None):
        self.key = key
        self.path = path
        self.ops = ops
        self.coerce = coerce
        self.label = label
        self.group = group
        self.kind = kind
        self.choices = choices or []
        # Fields that cannot be expressed in SQL and are filtered in Python
        # after the queryset has already narrowed the population.
        self.post = post
        # 'null'  → present means NOT NULL
        # 'text'  → present means NOT NULL and not the empty string
        # 'exists'→ present means a related row exists
        self.presence = presence

    def as_json(self):
        return {
            "key": self.key, "label": self.label, "group": self.group,
            "kind": self.kind, "ops": self.ops, "choices": self.choices,
        }


RFM_SEGMENT_CHOICES = [
    "champion", "loyal", "cant_lose", "at_risk", "hibernating", "lost",
    "new", "promising", "potential_loyalist", "needs_attention", "about_to_sleep",
]
LAPSE_CHOICES = ["healthy", "due", "at_risk", "lapsed", "never"]
CONFIDENCE_CHOICES = ["none", "low", "medium", "high"]

FIELD_REGISTRY = {f.key: f for f in [
    # ── value ─────────────────────────────────────────────────────────────
    Field("lifetime_value", "lifetime_value", NUMERIC_OPS, _num,
          "Lifetime value", "Value"),
    Field("net_spend", "net_spend", NUMERIC_OPS, _num,
          "Spend (last 3 years)", "Value"),
    Field("avg_ticket", "avg_ticket", NUMERIC_OPS, _num,
          "Average bill", "Value"),
    Field("max_ticket", "max_ticket", NUMERIC_OPS, _num,
          "Largest bill", "Value"),

    # ── behaviour ─────────────────────────────────────────────────────────
    Field("purchase_count_all", "purchase_count_all", NUMERIC_OPS, _int,
          "Number of purchases", "Behaviour"),
    Field("days_since_last", "days_since_last", NUMERIC_OPS, _int,
          "Days since last purchase", "Behaviour"),
    Field("rfm_segment", "rfm_segment", CHOICE_OPS, _str,
          "RFM segment", "Behaviour", kind="choice", choices=RFM_SEGMENT_CHOICES),
    Field("lapse_band", "lapse_band", CHOICE_OPS, _str,
          "Lapse risk", "Behaviour", kind="choice", choices=LAPSE_CHOICES),
    Field("confidence", "confidence", CHOICE_OPS, _str,
          "Data confidence", "Behaviour", kind="choice", choices=CONFIDENCE_CHOICES),
    Field("r_score", "r_score", NUMERIC_OPS, _int, "Recency score", "Behaviour"),
    Field("f_score", "f_score", NUMERIC_OPS, _int, "Frequency score", "Behaviour"),
    Field("m_score", "m_score", NUMERIC_OPS, _int, "Monetary score", "Behaviour"),

    # ── what they buy ─────────────────────────────────────────────────────
    Field("top_category_id", "top_category_id", CHOICE_OPS, _int,
          "Favourite category", "Preferences", kind="number"),
    Field("top_purity_id", "top_purity_id", CHOICE_OPS, _int,
          "Favourite purity", "Preferences", kind="number"),

    # ── engagement ────────────────────────────────────────────────────────
    Field("engagement_score", "engagement_score", NUMERIC_OPS, _int,
          "Engagement score", "Engagement"),
    Field("catalog_views_90d", "catalog_views_90d", NUMERIC_OPS, _int,
          "Catalog views (90 days)", "Engagement"),

    # ── who they are ──────────────────────────────────────────────────────
    Field("city", "ledger__city", TEXT_OPS, _str, "City", "Profile", kind="text"),
    Field("state", "ledger__state", TEXT_OPS, _str, "State", "Profile", kind="text"),
    Field("b2b", "b2b", BOOL_OPS, _bool, "Is a B2B account", "Profile", kind="bool"),
    # Text presence must treat '' as absent, not just NULL — the ERP stores a
    # missing phone or email as an empty string far more often than as null.
    Field("has_mobile", "ledger__mobile1", BOOL_OPS, _bool,
          "Has a mobile number", "Profile", kind="bool", presence="text"),
    Field("has_email", "ledger__email", BOOL_OPS, _bool,
          "Has an email address", "Profile", kind="bool", presence="text"),
    Field("has_dob", "ledger__dob", BOOL_OPS, _bool,
          "Has a date of birth", "Profile", kind="bool", presence="null"),
    Field("tag", "ledger__intel_tags__tag_id", CHOICE_OPS, _int,
          "Has tag", "Profile", kind="number"),

    # ── relationships ─────────────────────────────────────────────────────
    Field("has_scheme", "ledger__scheme_enrollments", BOOL_OPS, _bool,
          "Enrolled in a savings scheme", "Relationships", kind="bool",
          presence="exists"),

    # ── evaluated in Python (see SegmentCompiler.post_filter) ─────────────
    Field("occasion_within_days", None, ["lte"], _int,
          "Birthday or anniversary within N days", "Occasions", post=True),
    Field("marketable", None, BOOL_OPS, _bool,
          "Can be sent marketing messages", "Consent", kind="bool", post=True),
]}


def _presence_q(field, present):
    """
    Compile a "has X" question.

    Presence is not simply `isnull=False`: this ERP records a missing phone or
    email as an empty string at least as often as null, so a text field must
    exclude both or the filter silently under-reports.
    """
    if field.presence == "text":
        q = Q(**{f"{field.path}__isnull": False}) & ~Q(**{field.path: ""})
    else:  # 'null' and 'exists' both hinge on the row/value existing
        q = Q(**{f"{field.path}__isnull": False})
    return q if present else ~q


class SegmentCompiler:
    """Turn a validated definition into a queryset over CustomerProfileSnapshot."""

    def __init__(self, retail, definition):
        self.retail = retail
        self.definition = definition or {}
        self.match = str(self.definition.get("match", "all")).lower()
        if self.match not in ("all", "any"):
            raise ValidationError("match must be 'all' or 'any'.")
        self.rules = self.definition.get("rules") or []
        if not isinstance(self.rules, list):
            raise ValidationError("rules must be a list.")

    def _compile_rule(self, rule):
        if not isinstance(rule, dict):
            raise ValidationError("Each rule must be an object.")

        key = rule.get("field")
        field = FIELD_REGISTRY.get(key)
        if field is None:
            raise ValidationError(f"Unknown field '{key}'.")

        op = rule.get("op", "eq")
        if op not in field.ops:
            raise ValidationError(
                f"Operator '{op}' is not allowed on '{key}'. "
                f"Allowed: {', '.join(field.ops)}."
            )

        raw = rule.get("value")
        value = _list(field.coerce)(raw) if op == "in" else field.coerce(raw)

        if field.kind == "choice" and field.choices:
            candidates = value if isinstance(value, list) else [value]
            for candidate in candidates:
                if candidate not in field.choices:
                    raise ValidationError(
                        f"'{candidate}' is not a valid value for '{key}'."
                    )

        if field.presence:
            return _presence_q(field, bool(value))

        lookup = f"{field.path}{OPS[op]}"
        q = Q(**{lookup: value})
        return ~q if op == "ne" else q

    def _validate_all(self):
        """Reject unknown fields up front, including Python-side ones."""
        for rule in self.rules:
            if not isinstance(rule, dict):
                raise ValidationError("Each rule must be an object.")
            if rule.get("field") not in FIELD_REGISTRY:
                raise ValidationError(f"Unknown field '{rule.get('field')}'.")

    def sql_rules(self):
        self._validate_all()
        return [r for r in self.rules if not FIELD_REGISTRY[r["field"]].post]

    def post_rules(self):
        self._validate_all()
        return [r for r in self.rules if FIELD_REGISTRY[r["field"]].post]

    def base_queryset(self):
        return (
            CustomerProfileSnapshot.objects
            .filter(retail=self.retail)
            .select_related("ledger")
        )

    def queryset(self):
        """
        The SQL-expressible part of the definition.

        Note this is NOT the answer on its own when there are Python-side rules
        — see `evaluate()`, which combines the two halves correctly for both
        'all' and 'any'.
        """
        qs = self.base_queryset()

        combined = None
        for rule in self.sql_rules():
            q = self._compile_rule(rule)
            if combined is None:
                combined = q
            elif self.match == "all":
                combined &= q
            else:
                combined |= q

        if combined is not None:
            qs = qs.filter(combined)

        # Joins across to-many relations (tags, schemes) can duplicate rows.
        return qs.distinct()

    def post_filter(self, snapshots, today=None):
        """
        Apply the predicates that SQL cannot express portably.

        `occasion_within_days` has to wrap around the year boundary (28 Dec →
        3 Jan is 6 days apart, not 359), which no portable date expression
        handles. It runs last, over the already-narrowed population.
        """
        rules = self.post_rules()
        if not rules:
            return list(snapshots)

        today = today or date.today()
        out = []
        for snapshot in snapshots:
            verdicts = [self._post_verdict(rule, snapshot, today) for rule in rules]
            keep = all(verdicts) if self.match == "all" else any(verdicts)
            if keep:
                out.append(snapshot)
        return out

    @staticmethod
    def _post_verdict(rule, snapshot, today):
        key = rule["field"]
        field = FIELD_REGISTRY[key]
        value = field.coerce(rule.get("value"))
        ledger = snapshot.ledger

        if key == "occasion_within_days":
            gaps = [
                days_until_this_year(d.month, d.day, today)
                for d in (ledger.dob, ledger.anniversary) if d
            ]
            return bool(gaps) and min(gaps) <= value

        if key == "marketable":
            social = getattr(ledger, "social_profile", None)
            marketable = True if social is None else social.is_marketable_whatsapp
            return marketable is bool(value)

        return True


def evaluate(segment_or_definition, retail, today=None):
    """
    Members of a segment, honouring both SQL and Python predicates.

    The two halves combine differently depending on `match`:

      all  →  SQL narrows the population, then the Python rules filter it
              further. Intersection; cheap.
      any  →  a customer matching only a Python rule must still be included,
              so narrowing by SQL first would wrongly exclude them. Both halves
              are evaluated over the population and unioned.

    Returns a list of CustomerProfileSnapshot with `ledger` selected.
    """
    definition = (
        segment_or_definition.definition
        if hasattr(segment_or_definition, "definition")
        else segment_or_definition
    )
    compiler = SegmentCompiler(retail, definition)
    post_rules = compiler.post_rules()

    if not post_rules:
        return list(compiler.queryset())

    if compiler.match == "all":
        qs = compiler.queryset().select_related("ledger__social_profile")
        return compiler.post_filter(qs, today)

    # match == 'any': union of the SQL matches and the Python matches.
    sql_ids = set(compiler.queryset().values_list("id", flat=True)) \
        if compiler.sql_rules() else set()
    population = (
        compiler.base_queryset().select_related("ledger__social_profile")
    )
    matched = compiler.post_filter(population, today)
    matched_ids = {s.id for s in matched}

    return [s for s in population if s.id in sql_ids or s.id in matched_ids]


def registry_json():
    """The filterable-field catalogue, for the segment builder UI."""
    groups = {}
    for field in FIELD_REGISTRY.values():
        groups.setdefault(field.group, []).append(field.as_json())
    return [{"group": name, "fields": fields} for name, fields in groups.items()]
