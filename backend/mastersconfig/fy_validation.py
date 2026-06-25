from rest_framework.exceptions import ValidationError


def assert_date_in_active_fy(retail, txn_date, field="date1"):
    """Raise ValidationError if txn_date is outside the retail's active fiscal year.
    No-op when there is no active FY or no date is supplied (callers that require a
    date enforce presence separately)."""
    fy = getattr(retail, "active_fy", None) if retail is not None else None
    if fy is None or txn_date is None:
        return None
    if not (fy.fy_start <= txn_date <= fy.fy_end):
        raise ValidationError({
            field: (
                f"Date {txn_date} is outside the active fiscal year "
                f"{fy.fy_code} ({fy.fy_start} to {fy.fy_end})."
            )
        })
    return None
