class BusinessRuleError(Exception):
    """A rule from the BRD (BR-xx) refused the operation. Nothing was saved."""


class PeriodLocked(BusinessRuleError):
    """The date falls in a locked period (BR-20)."""


class FactoryNotAllowed(BusinessRuleError):
    """The user may not post to or see this factory (BR-23)."""
