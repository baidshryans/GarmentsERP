from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.utils.timezone import make_aware

from goldrates.serializer import PurityMasterSerializer
from .models import *
from django.contrib.auth.decorators import login_required
from userauth import views
from datetime import datetime, timedelta
from django.utils import timezone
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView
# Create your views here.

class PurityMasterView(ListCreateAPIView):
    serializer_class = PurityMasterSerializer
    queryset = PurityMaster.objects.all()
    pagination_class = None


class PurityMasterDetailView(RetrieveUpdateDestroyAPIView):
    serializer_class = PurityMasterSerializer
    queryset = PurityMaster.objects.all()



from django.db.models import Max, Subquery, OuterRef
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import GoldRates, PurityMaster
from .serializer import GoldRatesSerializer
from django.db import transaction
from django.core.cache import cache

GOLD_RATE_CACHE_TTL = 300  # 5 minutes

class RecentGoldRatesView(APIView):
    def get(self, request):
        requested_date = request.query_params.get('date', '')
        cache_key = f'gold_rates_{requested_date}'

        cached = cache.get(cache_key)
        if cached is not None:
            return Response(cached, status=status.HTTP_200_OK)

        if requested_date:
            try:
                parsed_date = make_aware(datetime.strptime(requested_date, '%Y-%m-%d'))
                parsed_date = parsed_date + timedelta(days=1)
                gold_rates = GoldRates.objects.filter(date1__lt=parsed_date)
            except ValueError:
                return Response({'error': 'Invalid date format'}, status=status.HTTP_400_BAD_REQUEST)
        else:
            gold_rates = GoldRates.objects.all()

        latest_rates = gold_rates.filter(
            date1=Subquery(
                gold_rates.filter(purity=OuterRef('purity'))
                .order_by('-date1')
                .values('date1')[:1]
            )
        )

        serializer = GoldRatesSerializer(latest_rates, many=True)
        cache.set(cache_key, serializer.data, GOLD_RATE_CACHE_TTL)
        return Response(serializer.data, status=status.HTTP_200_OK)

class GoldRatesView(ListCreateAPIView):
    serializer_class = GoldRatesSerializer
    queryset = GoldRates.objects.all()

class UpdateGoldRateView(APIView):
    def post(self, request):
        with transaction.atomic():
            data = request.data
            if not isinstance(data, list):
                data = [data]

            serializer = GoldRatesSerializer(data=data, many=True)
            if serializer.is_valid():
                serializer.save()
                # Invalidate gold rate cache so the ticker picks up new rates
                today = timezone.now().strftime('%Y-%m-%d')
                cache.delete(f'gold_rates_{today}')
                cache.delete('gold_rates_')  # no-date variant
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)