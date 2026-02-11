"""
Scheduler module — APScheduler setup for background cron jobs
"""
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.tasks.membership_jobs import (
    job_send_expiry_reminders,
    job_expire_memberships,
    job_auto_renew_memberships,
)

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()


def start_scheduler():
    """Register all cron jobs and start the scheduler."""

    # 1) Kirim reminder email H-7 dan H-3 sebelum membership expired
    #    Jalan setiap hari jam 08:00
    scheduler.add_job(
        job_send_expiry_reminders,
        trigger=CronTrigger(hour=8, minute=0),
        id="send_expiry_reminders",
        name="Send membership expiry reminders",
        replace_existing=True,
    )

    # 2) Tandai membership yang sudah lewat end_date sebagai expired
    #    Jalan setiap hari jam 00:05
    scheduler.add_job(
        job_expire_memberships,
        trigger=CronTrigger(hour=0, minute=5),
        id="expire_memberships",
        name="Expire ended memberships",
        replace_existing=True,
    )

    # 3) Auto-renew membership yang auto_renew=1 dan expired hari ini
    #    Jalan setiap hari jam 00:30 (setelah expire job)
    scheduler.add_job(
        job_auto_renew_memberships,
        trigger=CronTrigger(hour=0, minute=30),
        id="auto_renew_memberships",
        name="Auto-renew memberships",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("Scheduler started with %d jobs", len(scheduler.get_jobs()))


def stop_scheduler():
    """Shutdown the scheduler gracefully."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")
