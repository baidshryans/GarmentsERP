"""Vendor analytics API views."""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated


class VendorDashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({'status': 'placeholder'})


class StockAgeingView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({'status': 'placeholder'})


class DesignPerformanceView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({'status': 'placeholder'})


class InventoryTurnoverView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({'status': 'placeholder'})


class ItemPerformanceView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({'status': 'placeholder'})
