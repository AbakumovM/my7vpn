# utils/scheduler.py
import zoneinfo
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from utils.background_tasks import check_pending_subscriptions
from apscheduler.triggers.cron import CronTrigger


def setup_scheduler(bot):
    tz = zoneinfo.ZoneInfo("Asia/Yekaterinburg")
    scheduler = AsyncIOScheduler(timezone=tz)

    scheduler.add_job(
        check_pending_subscriptions,
        trigger=CronTrigger(hour=9, minute=0),
        kwargs={"bot": bot},
        id="check_subscriptions",
        max_instances=1,
    )

    return scheduler
