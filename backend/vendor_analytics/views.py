"""Vendor analytics API views."""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from .services import (
    VendorDashboardService,
    StockAgeingService,
    DesignPerformanceService,
    InventoryTurnoverService,
    ItemPerformanceService,
)


def _get_retail_id(request):
    """
    Extract the retail ID from request.retail (set by RetailMiddleware).

    Raises ValueError if retail is not available on the request.
    """
    retail = getattr(request, 'retail', None)
    if retail is None:
        raise ValueError("retail_id not found")
    return retail.id


def _parse_params(request):
    """Extract and validate shared query params."""
    return {
        'vendor_id': request.query_params.get('vendor_id'),
        'from_date': request.query_params.get('from_date'),
        'to_date': request.query_params.get('to_date'),
        'item_type': request.query_params.get('item_type'),
        'purity_id': request.query_params.get('purity_id'),
        'design_code': request.query_params.get('design_code'),
    }


class VendorDashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            retail_id = _get_retail_id(request)
        except ValueError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        params = _parse_params(request)
        vendor_id = params.pop('vendor_id')
        if not vendor_id:
            return Response(
                {'error': 'vendor_id is required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            data = VendorDashboardService(retail_id, vendor_id, **params).get_data()
            return Response(data, status=status.HTTP_200_OK)
        except Exception as exc:
            return Response({'error': str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class StockAgeingView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            retail_id = _get_retail_id(request)
        except ValueError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        params = _parse_params(request)
        vendor_id = params.pop('vendor_id')
        if not vendor_id:
            return Response(
                {'error': 'vendor_id is required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            data = StockAgeingService(retail_id, vendor_id, **params).get_data()
            return Response(data, status=status.HTTP_200_OK)
        except Exception as exc:
            return Response({'error': str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class DesignPerformanceView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            retail_id = _get_retail_id(request)
        except ValueError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        params = _parse_params(request)
        vendor_id = params.pop('vendor_id')
        if not vendor_id:
            return Response(
                {'error': 'vendor_id is required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            data = DesignPerformanceService(retail_id, vendor_id, **params).get_data()
            return Response(data, status=status.HTTP_200_OK)
        except Exception as exc:
            return Response({'error': str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class InventoryTurnoverView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            retail_id = _get_retail_id(request)
        except ValueError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        params = _parse_params(request)
        vendor_id = params.pop('vendor_id')
        if not vendor_id:
            return Response(
                {'error': 'vendor_id is required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            data = InventoryTurnoverService(retail_id, vendor_id, **params).get_data()
            return Response(data, status=status.HTTP_200_OK)
        except Exception as exc:
            return Response({'error': str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ItemPerformanceView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            retail_id = _get_retail_id(request)
        except ValueError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        params = _parse_params(request)
        vendor_id = params.pop('vendor_id')
        if not vendor_id:
            return Response(
                {'error': 'vendor_id is required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            data = ItemPerformanceService(retail_id, vendor_id, **params).get_data()
            return Response(data, status=status.HTTP_200_OK)
        except Exception as exc:
            return Response({'error': str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
