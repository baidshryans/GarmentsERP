"""Lighter entry forms: the one rule behind every "More options" section.

A form shows what is needed every time; the rest sits in a closed <details class="more"> on the same form. The
section opens by itself when a field inside holds something other than its default, or has an error, so nothing a
user entered is ever hidden. That rule lives here (`more_open`) and nowhere else:

- Django form pages name their folded fields in `more_fields` on the form class (and what the summary says in
  `more_label`); templates read them with `{% more_fields form as more %}`.
- Hand-written forms wrap the folded fields in `{% more "expected by, notes" open=... %} ... {% endmore %}` and get
  the flag from `{% more_open vals "expected_date remarks" as open %}`, or from `more_open()` called in the view
  when a default is not blank.
"""
from decimal import Decimal


def _plain(value) -> str:
    """One comparable text for a value, whether it came from a model, a form's initial data or a posted string.
    Nothing and False are "blank"; True is a ticked box."""
    if value is None or value is False:
        return ""
    if value is True:
        return "on"
    if hasattr(value, "pk"):
        return _plain(value.pk)
    if isinstance(value, (list, tuple, set, frozenset)):
        return ",".join(sorted(filter(None, (_plain(v) for v in value))))
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value).strip()


def _is_number(value) -> bool:
    return isinstance(value, (int, float, Decimal)) and not isinstance(value, bool)


def _number(value):
    """The value as a Decimal (blank is zero), or None when it is not a plain finite number."""
    if value is None or value is False or (isinstance(value, str) and not value.strip()):
        return Decimal(0)
    try:
        number = Decimal(str(value).strip().replace(",", ""))
        return number if number.is_finite() else None
    except (ArithmeticError, ValueError):
        return None


def differs(value, default="") -> bool:
    """Does a field hold something other than its default? Numbers are compared as numbers (0, "0.00" and blank are
    the same amount) only when the field is numeric: its default, or the value a model gave, is a number. In a text
    field "0" or "000" is something the user typed, and counts."""
    if _is_number(default) or _is_number(value):
        a, b = _number(value), _number(default)
        if a is not None and b is not None:
            return a != b
    return _plain(value) != _plain(default)


def more_open(values, defaults, errors=()) -> bool:
    """Should a folded section start open? Yes when any field inside differs from its default or has an error.

    values: a mapping of field name to its current value (a dict, a QueryDict, or None for a blank form).
    defaults: a mapping of field name to its default, or just the names when every default is blank.
    errors: names of fields that have an error."""
    if not isinstance(defaults, dict):
        defaults = dict.fromkeys(defaults, "")
    if any(name in defaults for name in errors):
        return True
    if values is None:
        return False
    return any(differs(values.get(name), default) for name, default in defaults.items())


def _blank_values(form, names):
    """What a brand-new form of this class shows in these fields: the defaults a value is compared with."""
    if not names:
        return {}
    try:
        fresh = type(form)()
    except TypeError:                       # a form that needs arguments: fall back to each field's own initial
        return {n: form.fields[n].initial for n in names}
    return {n: fresh[n].value() if n in fresh.fields else "" for n in names}


def more_form(form) -> dict:
    """The folded part of a Django form: its bound fields, their names, and whether the section starts open."""
    names = [n for n in getattr(form, "more_fields", ()) if n in form.fields]
    defaults = {**_blank_values(form, names), **getattr(form, "more_defaults", {})}
    values = {n: form[n].value() for n in names}
    errors = [n for n in names if form[n].errors] if form.is_bound else []
    return {"fields": [form[n] for n in names], "names": names, "label": getattr(form, "more_label", ""),
            "open": more_open(values, {n: defaults.get(n, "") for n in names}, errors)}
