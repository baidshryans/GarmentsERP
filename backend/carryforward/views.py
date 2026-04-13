import subprocess
import sys
from datetime import datetime

from django.conf import settings
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import CarryForwardLog


@api_view(['POST'])
def carry_forward_preview(request):
    """Run the management command in dry-run mode and return the stats."""
    cutoff_date = request.data.get('cutoff_date')
    retail_id = request.data.get('retail_id')

    if not cutoff_date:
        return Response({"error": "cutoff_date is required"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        datetime.strptime(cutoff_date, '%Y-%m-%d')
    except ValueError:
        return Response({"error": "Invalid date format. Use YYYY-MM-DD."}, status=status.HTTP_400_BAD_REQUEST)

    cmd = [sys.executable, 'manage.py', 'carry_forward', '--cutoff-date', cutoff_date, '--dry-run']
    if retail_id:
        cmd += ['--retail-id', str(retail_id)]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True, text=True, timeout=120,
            cwd=str(settings.BASE_DIR),
        )
        return Response({
            "output": result.stdout,
            "errors": result.stderr,
            "returncode": result.returncode,
        })
    except subprocess.TimeoutExpired:
        return Response({"error": "Preview timed out"}, status=status.HTTP_504_GATEWAY_TIMEOUT)


@api_view(['POST'])
def carry_forward_execute(request):
    """Run the carry-forward for real. This replaces the database."""
    cutoff_date = request.data.get('cutoff_date')
    retail_id = request.data.get('retail_id')

    if not cutoff_date:
        return Response({"error": "cutoff_date is required"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        datetime.strptime(cutoff_date, '%Y-%m-%d')
    except ValueError:
        return Response({"error": "Invalid date format. Use YYYY-MM-DD."}, status=status.HTTP_400_BAD_REQUEST)

    cmd = [sys.executable, 'manage.py', 'carry_forward', '--cutoff-date', cutoff_date]
    if retail_id:
        cmd += ['--retail-id', str(retail_id)]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True, text=True, timeout=600,
            cwd=str(settings.BASE_DIR),
        )
        return Response({
            "output": result.stdout,
            "errors": result.stderr,
            "returncode": result.returncode,
            "success": result.returncode == 0,
        })
    except subprocess.TimeoutExpired:
        return Response({"error": "Carry-forward timed out"}, status=status.HTTP_504_GATEWAY_TIMEOUT)


@api_view(['GET'])
def carry_forward_log(request):
    """Return the list of past carry-forward events."""
    logs = CarryForwardLog.objects.all().values(
        'id', 'cutoff_date', 'old_db_filename', 'new_fy_code',
        'created_at', 'status', 'master_rows_copied', 'live_rows_copied',
        'ledgers_with_opening', 'notes',
        'retail__retail_code', 'retail__retail_name',
    )
    return Response(list(logs))
