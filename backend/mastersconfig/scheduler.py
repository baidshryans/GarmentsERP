"""
APScheduler background scheduler for CRM automation.
Runs every minute, checks all enabled CRMSettings, and fires occasion messages
when the configured send_time is reached (within the current minute) and
the messages have not already been sent today.
"""
import logging
from datetime import date, datetime

logger = logging.getLogger(__name__)

_scheduler = None


def start():
    """Start the background scheduler. Safe to call multiple times."""
    global _scheduler
    if _scheduler and _scheduler.running:
        return
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.interval import IntervalTrigger

        _scheduler = BackgroundScheduler(timezone='Asia/Kolkata')
        _scheduler.add_job(
            run_crm_scheduler,
            trigger=IntervalTrigger(minutes=1),
            id='crm_daily_sender',
            replace_existing=True,
            max_instances=1,
            misfire_grace_time=59,
        )
        _scheduler.start()
        logger.info("CRM APScheduler started (interval: 1 min)")
    except ImportError:
        logger.warning(
            "APScheduler not installed — CRM automation disabled. "
            "Run: pip install apscheduler"
        )
    except Exception as e:
        logger.error(f"Failed to start CRM scheduler: {e}", exc_info=True)


def stop():
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("CRM APScheduler stopped")


def run_crm_scheduler():
    """
    Called every minute by APScheduler.
    Iterates all enabled CRMSettings and sends messages when:
      1. Current hour:minute matches the configured send_time, AND
      2. last_send_date is not today (prevents duplicate sends).
    """
    try:
        # Avoid Django startup import issues
        from mastersconfig.models import CRMSettings
        from contacts.crm_sender import send_occasions_for_retail

        now = datetime.now()
        today = date.today()

        enabled = CRMSettings.objects.select_related('retail').filter(is_enabled=True)
        for setting in enabled:
            t = setting.send_time
            if t.hour == now.hour and t.minute == now.minute and setting.last_send_date != today:
                logger.info(f"CRM: firing for retail '{setting.retail.retail_name}'")
                try:
                    send_occasions_for_retail(setting)
                except Exception as e:
                    logger.error(
                        f"CRM: error sending for retail {setting.retail_id}: {e}",
                        exc_info=True,
                    )
    except Exception as e:
        logger.error(f"CRM scheduler tick error: {e}", exc_info=True)
