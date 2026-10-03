from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import Factory
from core.scoping import FactoryScopedViewMixin
from ledger.models import Voucher


class MeView(APIView):
    """Who am I and which factories may I use. Used by the PWA after sign-in."""

    def get(self, request):
        user = request.user
        return Response({
            "username": user.get_username(),
            "roles": list(user.roles.values_list("name", flat=True)),
            "factories": [
                {"id": f.pk, "code": f.code, "name": f.name}
                for f in Factory.objects.for_user(user).filter(is_active=True)
            ],
        })


class VoucherListView(FactoryScopedViewMixin, APIView):
    """Read-only voucher list, always filtered to the caller's factories (BR-23)."""

    queryset = Voucher.objects.all()

    def get(self, request):
        if not request.user.has_screen_perm("ledger.voucher", "view"):
            return Response({"detail": "Not permitted."}, status=403)
        rows = self.get_queryset().filter(status="posted").values(
            "id", "number", "voucher_type", "date", "total", "factory__code"
        )[:200]
        return Response(list(rows))
