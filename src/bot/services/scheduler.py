"""
Scheduler service for automated bot tasks.

This module manages periodic tasks like auto-restricting users who exceed
time thresholds for profile completion.
"""

import logging
from datetime import UTC, datetime

from apscheduler.schedulers.background import BackgroundScheduler
from telegram.ext import Application

from bot.config import get_settings
from bot.constants import (
    RESTRICTED_PERMISSIONS,
    RESTRICTION_MESSAGE_AFTER_TIME,
    format_threshold_display,
)
from bot.database.service import get_database
from bot.services.bot_info import BotInfoCache

logger = logging.getLogger(__name__)


def _auto_restrict_sync_wrapper(application: Application) -> None:
    """Synchronous wrapper for async auto-restriction job.
    
    BackgroundScheduler runs jobs synchronously in a thread pool.
    This wrapper uses asyncio.run() to execute the async function.
    
    Args:
        application: Telegram application for sending messages.
    """
    import asyncio

    asyncio.run(auto_restrict_expired_warnings(application))


async def auto_restrict_expired_warnings(application: Application) -> None:
    """
    Periodically check and restrict users who exceeded time threshold.

    Finds all active warnings past the configured hours threshold and
    applies restrictions (mutes) to those users.

    Args:
        application: Telegram application for sending messages.
    """
    settings = get_settings()
    db = get_database()

    # Get warnings that exceeded time threshold
    expired_warnings = db.get_warnings_past_time_threshold(
        settings.warning_time_threshold_minutes
    )

    if not expired_warnings:
        logger.debug("No expired warnings to process")
        return

    logger.info(f"Processing {len(expired_warnings)} expired warnings")

    # Get bot username once for all DM links
    bot = application.bot
    bot_username = await BotInfoCache.get_username(bot)
    dm_link = f"https://t.me/{bot_username}"

    for warning in expired_warnings:
        try:
            # Apply restriction
            await bot.restrict_chat_member(
                chat_id=settings.group_id,
                user_id=warning.user_id,
                permissions=RESTRICTED_PERMISSIONS,
            )
            db.mark_user_restricted(warning.user_id, settings.group_id)

            # Send notification to warning topic
            threshold_display = format_threshold_display(
                settings.warning_time_threshold_minutes
            )
            restriction_message = RESTRICTION_MESSAGE_AFTER_TIME.format(
                user_id=warning.user_id,
                threshold_display=threshold_display,
                rules_link=settings.rules_link,
                dm_link=dm_link,
            )
            await bot.send_message(
                chat_id=settings.group_id,
                message_thread_id=settings.warning_topic_id,
                text=restriction_message,
                parse_mode="Markdown",
            )

            logger.info(
                f"Auto-restricted user {warning.user_id} after {settings.warning_time_threshold_minutes} minutes"
            )
        except Exception as e:
            logger.error(
                f"Error auto-restricting user {warning.user_id}: {e}", exc_info=True
            )


def start_scheduler(application: Application) -> BackgroundScheduler:
    """
    Initialize and start the APScheduler scheduler.

    Registers periodic tasks like auto-restriction job.
    Uses BackgroundScheduler which runs in a background thread and doesn't
    require a running event loop.

    Args:
        application: Telegram application for passing to scheduled jobs.

    Returns:
        BackgroundScheduler: Started scheduler instance.
    """
    settings = get_settings()
    scheduler = BackgroundScheduler()

    # Add job to check expired warnings every 5 minutes
    scheduler.add_job(
        _auto_restrict_sync_wrapper,
        "interval",
        minutes=5,
        args=[application],
        id="auto_restrict_job",
        name="Auto-restrict users past time threshold",
    )

    scheduler.start()
    logger.info("Scheduler started with auto-restriction job (every 5 minutes)")
    return scheduler
