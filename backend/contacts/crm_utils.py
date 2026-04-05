from datetime import date


def clean_mobile(raw):
    """
    Strip country code prefix and non-digits. Returns local digits or None.
    Handles formats:
      "+91 9876543210"  (new format stored by PhoneInput component)
      "+919876543210"   (legacy — no space)
      "9876543210"      (bare local number)
      "09876543210"     (leading zero)
    """
    if not raw:
        return None
    raw = raw.strip()
    # New format: "+<dial> <local>" — strip everything before the first space
    if raw.startswith('+') and ' ' in raw:
        raw = raw.split(' ', 1)[1]
    digits = ''.join(c for c in raw if c.isdigit())
    # Legacy: +91 prefix merged without space (e.g. "+919876543210" → "919876543210")
    if digits.startswith('91') and len(digits) == 12:
        digits = digits[2:]
    if digits.startswith('0') and len(digits) == 11:
        digits = digits[1:]
    return digits if len(digits) >= 7 else None


def get_mobile(ledger):
    """Return first valid 10-digit mobile from ledger fields."""
    for field in ('mobile1', 'mobile2', 'mobile3', 'phone1'):
        cleaned = clean_mobile(getattr(ledger, field, None))
        if cleaned:
            return cleaned
    return None


def days_until_this_year(month, day, today=None):
    """Days from today until the next occurrence of (month, day)."""
    if today is None:
        today = date.today()
    try:
        target = today.replace(month=month, day=day)
    except ValueError:
        target = today.replace(month=2, day=28)
    if target < today:
        try:
            target = target.replace(year=today.year + 1)
        except ValueError:
            target = date(today.year + 1, 2, 28)
    return (target - today).days


def build_message(name, occasion, retail_name):
    """Build a personalised WhatsApp greeting message."""
    if occasion == 'birthday':
        return (
            f"Happy Birthday {name}! \U0001f382 Wishing you a wonderful day filled with joy and happiness.\n"
            f"As a special gift from us, enjoy 20% off on making charges on your next visit.\n"
            f"Valid for 30 days. See you soon!\n\u2014 {retail_name}"
        )
    else:
        return (
            f"Happy Anniversary {name}! \U0001f48d Wishing you and your loved ones a beautiful celebration.\n"
            f"We'd love to be part of your special day \u2014 enjoy 20% off on making charges on your next purchase.\n"
            f"Valid for 30 days. With warm regards,\n\u2014 {retail_name}"
        )
