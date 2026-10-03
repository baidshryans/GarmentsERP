"""E-way bill interface. A real GSP provider is chosen later (PRD 8.1); until then the stub refuses cleanly,
and the e-way bill number can be typed in on the document."""
from typing import Protocol


class EwayBillNotConfigured(Exception):
    """No GSP is connected, so an e-way bill cannot be generated automatically."""


class EwayBillProvider(Protocol):
    def generate(self, document) -> str:
        """Return the e-way bill number for a document, or raise."""


class NullEwayBillProvider:
    def generate(self, document) -> str:
        raise EwayBillNotConfigured("No e-way bill provider is connected yet. Enter the e-way bill number by hand.")


def get_provider() -> EwayBillProvider:
    return NullEwayBillProvider()
