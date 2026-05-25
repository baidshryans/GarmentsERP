"""
Gunicorn configuration for Jewel India ERP.

Usage:
    gunicorn -c gunicorn.conf.py jewel_test.wsgi:application

Tune via environment variables so the same file works across machines:
    WEB_CONCURRENCY   — override worker count  (default: (2 × CPU) + 1)
    GUNICORN_TIMEOUT  — worker timeout seconds  (default: 120)
    GUNICORN_PORT     — bind port               (default: 8000)
"""
import multiprocessing
import os

# ── Binding ──────────────────────────────────────────────────────────────────
port = os.environ.get("GUNICORN_PORT", "8000")
bind = f"0.0.0.0:{port}"

# ── Worker count ─────────────────────────────────────────────────────────────
# (2 × CPU cores) + 1 is the standard formula for I/O-bound Django apps.
# Each synchronous worker handles exactly one request at a time.
# For 100 concurrent users without async, you need ~100 workers — which means
# switching to gevent or uvicorn async workers (see worker_class below).
workers = int(os.environ.get("WEB_CONCURRENCY", multiprocessing.cpu_count() * 2 + 1))

# ── Worker class ─────────────────────────────────────────────────────────────
# Options:
#   sync       — default, 1 request/worker at a time.  Safe with SQLite.
#   gevent     — green-thread async (pip install gevent).  Handles 100+ concurrent
#                requests with far fewer workers.  Safe for Django with SQLite.
#   uvicorn.workers.UvicornWorker — full async (pip install uvicorn[standard]).
#                Requires ASGI; use when migrating to PostgreSQL + async Django.
#
# For 100 concurrent users on SQLite: switch to gevent now.
# Once on PostgreSQL + ASGI: switch to UvicornWorker.
worker_class = os.environ.get("GUNICORN_WORKER_CLASS", "gevent")

# Greenlets per gevent worker — each greenlet handles one concurrent request.
# With 4 workers × 50 connections = 200 effective concurrent slots.
worker_connections = int(os.environ.get("GUNICORN_WORKER_CONNECTIONS", "50"))

# ── Timeouts ─────────────────────────────────────────────────────────────────
# How long a worker can handle a request before being forcibly killed.
# Heavy reports (P&L, trial balance) can take 5–15 s; 120 s is conservative.
timeout = int(os.environ.get("GUNICORN_TIMEOUT", "120"))

# How long a worker can be idle during graceful shutdown.
graceful_timeout = 30

# How long to wait for a connection before giving up (keep-alive).
keepalive = 5

# ── Logging ──────────────────────────────────────────────────────────────────
accesslog = os.environ.get("GUNICORN_ACCESS_LOG", "-")   # "-" = stdout
errorlog  = os.environ.get("GUNICORN_ERROR_LOG",  "-")
loglevel  = os.environ.get("GUNICORN_LOG_LEVEL",  "info")

# Log request duration so slow endpoints are easy to spot.
access_log_format = '%(h)s "%(r)s" %(s)s %(b)sB %(D)sµs'

# ── Process naming ───────────────────────────────────────────────────────────
proc_name = "jewel-erp"

# ── Restart workers that grow too large in memory ────────────────────────────
# Restart a worker after it has served this many requests (helps with memory
# leaks in long-running processes).
max_requests = 1000
max_requests_jitter = 100   # Stagger restarts so not all workers restart at once

# ── Pre-load the app once before forking workers ─────────────────────────────
# Saves ~50–100 MB RAM when workers share the app's loaded code (copy-on-write).
# Disable if using signals that don't survive fork (rare).
preload_app = True
