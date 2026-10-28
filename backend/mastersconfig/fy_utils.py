"""
Fiscal year utilities for enforcing FY closure rules.

Two-stage close model:
  Soft-close (is_closed=True):
      Routine transactions blocked. Journal entries (JRNL) still allowed for
      year-end provisions, depreciation, audit adjustments. Stays open for
      30-60 days after FY end.

  Hard-close (is_hard_closed=True):
      Absolute lock — no entries of any kind. Triggered after all adjustments
      are done and opening balances of the next FY have been synced.
      Can be toggled off temporarily to post further adjustments, then re-synced
      and re-hard-closed as many times as needed.
"""

from rest_framework.exceptions import ValidationError


# Voucher types that are allowed when soft-closed (is_closed=True)
ALWAYS_ALLOWED_TYPES = {'JRNL'}


def check_fy_open_for_transaction(retail, voucher_type=None):
    """
    Check if the active fiscal year allows this transaction type.
    Raises ValidationError if the FY is closed/hard-closed and the type is blocked.

    Args:
        retail: RetailMaster instance with active_fy loaded
        voucher_type: string like 'SV', 'PV', 'JRNL', etc. (optional)

    Returns:
        FiscalYearMaster instance (the active FY)
    """
    fy = getattr(retail, 'active_fy', None)
    if not fy:
        raise ValidationError(
            "No active fiscal year is set for this retail location. "
            "Please create and activate a fiscal year first."
        )

    # Hard-close: absolute lock, nothing allowed
    if fy.is_hard_closed:
        raise ValidationError(
            f"Fiscal year {fy.fy_code} is hard-closed. "
            f"No entries are permitted. Reopen the hard-close to post further adjustments."
        )

    # Soft-close: only journal entries allowed
    if fy.is_closed and voucher_type not in ALWAYS_ALLOWED_TYPES:
        raise ValidationError(
            f"Fiscal year {fy.fy_code} is closed. "
            f"Only journal entries are allowed in a soft-closed fiscal year."
        )

    return fy


def check_fy_allows_change(fy, voucher_type, action):
    """
    Guard for editing or deleting an EXISTING voucher in a specific fiscal year.

    `check_fy_open_for_transaction` only looks at the retail's active FY, which
    is the wrong year when someone opens an old bill by its direct URL. This
    takes the FY the voucher belongs to (or is being moved into).
    """
    if fy is None:
        return
    if fy.is_hard_closed:
        raise ValidationError(
            f"Fiscal year {fy.fy_code} is hard-closed. This voucher cannot be {action}. "
            f"Ask an administrator to reopen the fiscal year first."
        )
    if fy.is_closed and voucher_type not in ALWAYS_ALLOWED_TYPES:
        raise ValidationError(
            f"Fiscal year {fy.fy_code} is closed. This voucher cannot be {action}; "
            f"only journal entries are allowed in a closed fiscal year."
        )
