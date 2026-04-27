"""Vendor analytics API views."""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

class VendorDashboardView(APIView):
    def get(self, request):
        return Response({'status': 'placeholder'})

class StockAgeingView(APIView):
    def get(self, request):
        return Response({'status': 'placeholder'})

class DesignPerformanceView(APIView):
    def get(self, request):
        return Response({'status': 'placeholder'})

class InventoryTurnoverView(APIView):
    def get(self, request):
        return Response({'status': 'placeholder'})

class ItemPerformanceView(APIView):
    def get(self, request):
        return Response({'status': 'placeholder'})
