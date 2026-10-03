from core.exceptions import BusinessRuleError


class StockError(BusinessRuleError):
    """A stock operation was refused. Nothing was saved."""


class InsufficientStock(StockError):
    """The issue is more than is on hand (BR-02, BR-09)."""


class MovementImmutable(StockError):
    """Stock movements are an append-only ledger."""
