"""
AI Layer views — 4 endpoints:

  POST /ai/nl-query/           NLQueryView          — natural language → ERP data
  POST /ai/invoice-parse/      InvoiceParserView     — image/PDF → extracted JSON
  POST /ai/suggest-accounts/   AccountSuggestionView — narration → Dr/Cr suggestion
  GET  /ai/query-history/      NLQueryHistoryView    — paginated query log
"""

import logging

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination

from .models import NLQueryLog
from .services.nl_query import run_nl_query
from .services.invoice_parser import parse_invoice
from .services.account_suggester import suggest_accounts

logger = logging.getLogger(__name__)

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


class AIBaseView(APIView):
    """Base class: Token auth + authenticated users only."""
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get_retail(self):
        return getattr(self.request, "retail", None)


# ---------------------------------------------------------------------------
# 1. Natural Language Query
# ---------------------------------------------------------------------------

class NLQueryView(AIBaseView):
    """
    POST /ai/nl-query/
    Body: { "query": "What are total sales this month?" }
    Response: { "response": "...", "tool_calls": [...], "query_id": 123, "tokens_used": 450 }
    """

    def post(self, request):
        retail = self.get_retail()
        if not retail:
            return Response({"error": "Retail not found. Please select a retail first."}, status=400)

        query_text = request.data.get("query", "").strip()
        if not query_text:
            return Response({"error": "query field is required."}, status=400)

        if len(query_text) > 2000:
            return Response({"error": "Query too long. Maximum 2000 characters."}, status=400)

        result = run_nl_query(retail=retail, user=request.user, query_text=query_text)

        if "error" in result:
            return Response(result, status=500)

        return Response(result)


# ---------------------------------------------------------------------------
# 2. Invoice Parser
# ---------------------------------------------------------------------------

class InvoiceParserView(AIBaseView):
    """
    POST /ai/invoice-parse/   multipart/form-data, field: "file"
    Response: extracted invoice JSON
    """

    def post(self, request):
        retail = self.get_retail()
        if not retail:
            return Response({"error": "Retail not found."}, status=400)

        uploaded_file = request.FILES.get("file")
        if not uploaded_file:
            return Response({"error": "file field is required."}, status=400)

        if uploaded_file.size > MAX_FILE_SIZE:
            return Response({"error": "File too large. Maximum size is 10 MB."}, status=400)

        allowed_extensions = (".jpg", ".jpeg", ".png", ".webp", ".pdf")
        filename = uploaded_file.name.lower()
        if not any(filename.endswith(ext) for ext in allowed_extensions):
            return Response(
                {"error": "Unsupported file type. Allowed: JPG, PNG, WEBP, PDF."},
                status=400,
            )

        file_bytes = uploaded_file.read()
        result = parse_invoice(file_bytes=file_bytes, filename=uploaded_file.name)

        if "error" in result:
            return Response(result, status=500)

        return Response(result)


# ---------------------------------------------------------------------------
# 3. Account Suggestion
# ---------------------------------------------------------------------------

class AccountSuggestionView(AIBaseView):
    """
    POST /ai/suggest-accounts/
    Body: { "narration": "Paid BESCOM electricity bill", "voucher_type": "PMNT", "amount": 5000 }
    Response: { "debit_account": "...", "credit_account": "...", "confidence": 0.9, "reasoning": "..." }
    """

    def post(self, request):
        retail = self.get_retail()
        if not retail:
            return Response({"error": "Retail not found."}, status=400)

        narration = request.data.get("narration", "").strip()
        if not narration:
            return Response({"error": "narration field is required."}, status=400)

        voucher_type = request.data.get("voucher_type", "JRNL")
        try:
            amount = float(request.data.get("amount", 0) or 0)
        except (ValueError, TypeError):
            amount = 0.0

        result = suggest_accounts(
            retail=retail,
            narration=narration,
            voucher_type=voucher_type,
            amount=amount,
        )

        if "error" in result:
            return Response(result, status=500)

        return Response(result)


# ---------------------------------------------------------------------------
# 4. Query History
# ---------------------------------------------------------------------------

class NLQueryHistoryView(AIBaseView):
    """
    GET /ai/query-history/?page=1&page_size=20
    Returns paginated log of NL queries for this retail + user.
    """

    def get(self, request):
        retail = self.get_retail()
        if not retail:
            return Response({"error": "Retail not found."}, status=400)

        qs = NLQueryLog.objects.filter(retail=retail).order_by("-created_at")

        # Non-superusers see only their own queries
        if not request.user.is_superuser:
            qs = qs.filter(user=request.user)

        paginator = PageNumberPagination()
        paginator.page_size = min(int(request.query_params.get("page_size", 20)), 100)
        page = paginator.paginate_queryset(qs, request)

        data = [
            {
                "id": log.pk,
                "query": log.query_text[:200],
                "response": log.response_text[:500],
                "tokens_used": log.tokens_used,
                "tool_calls": log.tool_calls_json,
                "created_at": log.created_at.isoformat(),
                "user": log.user.username if log.user else None,
            }
            for log in page
        ]

        return paginator.get_paginated_response(data)
