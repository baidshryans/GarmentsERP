"""Background tasks for Customer 360, run by the django-tasks worker."""

import logging

from django_tasks import task

logger = logging.getLogger(__name__)


@task()
def rebuild_retail_profiles(retail_id, batch_size=None):
    """Rebuild every CustomerProfileSnapshot for one retail."""
    from customer_intel.services.snapshot import BATCH_SIZE, SnapshotBuilder

    builder = SnapshotBuilder(retail_id, batch_size=batch_size or BATCH_SIZE)
    result = builder.run()
    logger.info("rebuilt customer profiles for retail %s: %s", retail_id, result)
    return result


@task()
def send_campaign_message(recipient_id):
    """Send one campaign recipient. Enqueued by the per-minute drip."""
    from customer_intel.services.campaigns import send_one

    send_one(recipient_id)


@task()
def process_inbound_webhook(log_id):
    """
    Parse a stored provider payload.

    Runs out of band so the webhook endpoint can verify the signature, persist,
    and return 200 immediately — Meta retries aggressively on any non-200 and
    would otherwise duplicate the timeline.
    """
    from customer_intel.services.inbound import process_log

    process_log(log_id)
