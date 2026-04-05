"""
AccountSuggestionService — suggests debit/credit ledger accounts for a journal entry.

Given a narration string, voucher type, and optional amount, uses GPT-4o-mini
to pick the most likely debit and credit accounts from the active ledger list.
Ledger names are cached for 5 minutes to avoid repeated DB queries.
"""

import json
import logging

from django.conf import settings
from django.core.cache import cache
from openai import OpenAI

logger = logging.getLogger(__name__)

_client = None
CACHE_TIMEOUT = 300  # 5 minutes


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=settings.OPENAI_API_KEY)
    return _client


def _get_ledger_names(retail) -> list[str]:
    """
    Return a list of ledger account names for the given retail, cached for 5 min.
    """
    cache_key = f"ai_ledger_names_{retail.pk}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    from contacts.models import Ledger  # local import to avoid circular deps
    names = list(
        Ledger.objects.filter(retail=retail).values_list("ac_name", flat=True).order_by("ac_name")
    )
    cache.set(cache_key, names, CACHE_TIMEOUT)
    return names


SYSTEM_PROMPT = """You are a senior accountant for a jewellery business in India.
Given a transaction narration and voucher type, you must suggest the most appropriate
debit and credit ledger accounts from the provided list.

Rules:
1. Only use account names from the provided list. Do not invent new accounts.
2. For a Payment (PMNT): money goes OUT — typical debit is expense/asset, credit is Cash/Bank.
3. For a Receipt (RCPT): money comes IN — typical debit is Cash/Bank, credit is income/liability.
4. For a Journal (JRNL): follow standard double-entry bookkeeping.
5. For a Purchase (PRCH): debit the purchase/expense account, credit the supplier ledger.
6. For a Sale (SALE): debit the customer ledger, credit the sales account.
7. Confidence: 0.0 (wild guess) to 1.0 (certain).
8. Return ONLY valid JSON — no extra text.
"""

EXTRACTION_PROMPT = """Transaction details:
- Narration: {narration}
- Voucher type: {voucher_type}
- Amount: {amount}

Available ledger accounts:
{ledger_list}

Return JSON in this exact format:
{{
  "debit_account": "account name from the list",
  "credit_account": "account name from the list",
  "confidence": 0.85,
  "reasoning": "brief explanation"
}}"""


def suggest_accounts(retail, narration: str, voucher_type: str = "JRNL", amount: float = 0) -> dict:
    """
    Suggest debit/credit accounts for a transaction.

    Args:
        retail: RetailMaster instance (used to fetch ledger names)
        narration: Free-text narration entered by the user
        voucher_type: PMNT, RCPT, JRNL, PRCH, SALE, etc.
        amount: Transaction amount (informational only)

    Returns:
        dict with debit_account, credit_account, confidence, reasoning
        or {"error": "..."} on failure
    """
    if not settings.OPENAI_API_KEY:
        return {"error": "OpenAI API key not configured."}

    if not narration or not narration.strip():
        return {"error": "Narration is required."}

    ledger_names = _get_ledger_names(retail)
    if not ledger_names:
        return {"error": "No ledger accounts found for this retail."}

    # Limit the list to avoid exceeding token budget (take first 200 accounts)
    ledger_list_str = "\n".join(f"- {name}" for name in ledger_names[:200])

    prompt = EXTRACTION_PROMPT.format(
        narration=narration.strip(),
        voucher_type=voucher_type,
        amount=f"₹{amount:,.2f}" if amount else "not specified",
        ledger_list=ledger_list_str,
    )

    client = _get_client()

    try:
        response = client.chat.completions.create(
            model=settings.AI_NL_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            max_tokens=300,
            temperature=0.2,
        )

        raw_json = response.choices[0].message.content
        result = json.loads(raw_json)

        # Validate required keys
        for key in ("debit_account", "credit_account", "confidence", "reasoning"):
            if key not in result:
                result[key] = None

        # Validate suggested accounts exist in the list
        if result["debit_account"] not in ledger_names:
            result["debit_account_warning"] = f"'{result['debit_account']}' not found in ledger list"
        if result["credit_account"] not in ledger_names:
            result["credit_account_warning"] = f"'{result['credit_account']}' not found in ledger list"

        logger.info(
            "Account suggestion: debit=%s, credit=%s, confidence=%s",
            result.get("debit_account"),
            result.get("credit_account"),
            result.get("confidence"),
        )
        return result

    except json.JSONDecodeError as e:
        logger.error("GPT returned invalid JSON for account suggestion: %s", e)
        return {"error": f"Failed to parse AI response: {e}"}
    except Exception as e:
        logger.error("Account suggestion failed: %s", e)
        return {"error": str(e)}
