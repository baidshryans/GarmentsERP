"""
Advance every running or due campaign by one throttle-sized slice.

Runs every minute from the OS scheduler, alongside the existing `run_due_crm`
entry:

    python manage.py run_due_campaigns

Each pass claims at most `throttle_per_minute` recipients per campaign and
enqueues them onto the django-tasks worker, so a large campaign drains over
several minutes instead of hammering the provider in one burst.
"""

import logging

from django.core.management.base import BaseCommand
from django.utils import timezone

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Send the next slice of every running or scheduled campaign."

    def add_arguments(self, parser):
        parser.add_argument("--campaign-id", type=int, default=None)

    def handle(self, *args, **options):
        from customer_intel.models import Campaign
        from customer_intel.services.campaigns import drip

        due = Campaign.objects.filter(status="running")
        scheduled = Campaign.objects.filter(
            status="scheduled", scheduled_at__lte=timezone.now(),
        )
        campaigns = due | scheduled
        if options["campaign_id"]:
            campaigns = campaigns.filter(id=options["campaign_id"])

        total = 0
        for campaign in campaigns.distinct():
            try:
                count = drip(campaign.id)
                total += count
                if count:
                    logger.info("campaign %s: enqueued %d", campaign.id, count)
            except Exception as exc:
                # One broken campaign must not stall every other campaign.
                logger.error("campaign %s drip failed", campaign.id, exc_info=True)
                Campaign.objects.filter(id=campaign.id).update(
                    status="failed", last_error=str(exc)[:500],
                )

        self.stdout.write(f"run_due_campaigns: enqueued {total} message(s)")
