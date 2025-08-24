# utils/scheduler.py
import logging
import zoneinfo
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from utils.background_tasks import check_pending_subscriptions
from apscheduler.triggers.cron import CronTrigger
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
    return scheduler
