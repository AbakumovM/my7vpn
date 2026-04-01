# utils/scheduler.py
import logging
import zoneinfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from utils.background_tasks import check_pending_subscriptions, send_weekly_report

logger = logging.getLogger(__name__)


def setup_scheduler(bot):
    tz = zoneinfo.ZoneInfo("Asia/Yekaterinburg")
    scheduler = AsyncIOScheduler(timezone=tz)
    logger.info(f"🕒 Часовой пояс: {tz}")
    scheduler.add_job(
        check_pending_subscriptions,
        trigger=CronTrigger(hour=9, minute=0),
        kwargs={"bot": bot},
        id="check_subscriptions",
        max_instances=1,
    )
    scheduler.add_job(
        send_weekly_report,
        trigger=CronTrigger(day_of_week="mon", hour=10, minute=0),
        kwargs={"bot": bot},
        id="weekly_report",
        max_instances=1,
    )
    return scheduler
