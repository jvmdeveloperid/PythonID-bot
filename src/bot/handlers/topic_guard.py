"""
Warning topic guard for the PythonID bot.

This module protects the warning topic by deleting messages from
non-admin users. Only group administrators and the bot itself can
post in the warning topic.
"""

import logging

from telegram import Update
from telegram.ext import ContextTypes

from bot.config import get_settings

logger = logging.getLogger(__name__)


async def guard_warning_topic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Delete messages from non-admins in the warning topic.

    This handler runs with group=-1 (before other handlers) and deletes
    any messages in the warning topic that aren't from:
    - The bot itself
    - Group administrators or the group creator

    This keeps the warning topic clean for bot notifications only.

    Args:
        update: Telegram update containing the message.
        context: Bot context with helper methods.
    """
    # Skip if no message or sender
    if not update.message or not update.message.from_user:
        return

    settings = get_settings()

    # Only process messages from the configured group
    if update.effective_chat and update.effective_chat.id != settings.group_id:
        return

    # Only guard the warning topic, not other topics
    if update.message.message_thread_id != settings.warning_topic_id:
        return

    user = update.message.from_user
    bot_id = context.bot.id

    # Allow bot's own messages
    if user.id == bot_id:
        return

    # Check if user is an admin or creator
    chat_member = await context.bot.get_chat_member(
        chat_id=settings.group_id,
        user_id=user.id,
    )

    admin_statuses = ("administrator", "creator")
    if chat_member.status in admin_statuses:
        return

    # Delete message from non-admin user
    await update.message.delete()
    logger.info(
        f"Deleted message from non-admin user {user.id} ({user.full_name}) "
        f"in warning topic"
    )
