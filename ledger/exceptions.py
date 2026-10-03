from core.exceptions import BusinessRuleError, FactoryNotAllowed, PeriodLocked  # noqa: F401


class PostingError(BusinessRuleError):
    """A voucher could not be saved. Nothing was written."""


class Unbalanced(PostingError):
    """Debits do not equal credits (BR-24)."""


class FactoryRequired(PostingError):
    """Every voucher carries a factory (BR-24)."""


class InvalidLine(PostingError):
    """A voucher line is malformed: float amount, both or neither side, wrong precision, inactive ledger."""


class PostedVoucherImmutable(PostingError):
    """Posted vouchers are never edited or deleted; cancel by reversal (BR-16)."""


class NotReversible(PostingError):
    """Only a posted voucher that has not been reversed can be reversed."""
