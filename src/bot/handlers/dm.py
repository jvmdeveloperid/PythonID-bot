"""
DM (Direct Message) handler for the PythonID bot.

This module handles private messages to the bot, primarily for the
unrestriction flow. When a restricted user DMs the bot:
1. Check if user is in the group
2. Check if user now has complete profile
3. If restricted by bot and profile complete, unrestrict them
"""

import logging

from telegram import Update
from telegram.error import BadRequest, Forbidden
from telegram.ext import ContextTypes

from bot.config import get_settings
from bot.database.service import get_database
from bot.services.user_checker import check_user_profile

logger = logging.getLogger(__name__)


async def _get_user_status(
    context: ContextTypes.DEFAULT_TYPE, group_id: int, user_id: int
) -> str | None:
    """
    Get user's membership status in the group.

    Args:
        context: Bot context.
        group_id: Telegram group ID.
        user_id: Telegram user ID.

    Returns:
        str | None: User status ("member", "restricted", "left", "kicked", etc.)
            or None if unable to fetch (e.g., bot not in group).
    """
    try:
        user_member = await context.bot.get_chat_member(
            chat_id=group_id,
            user_id=user_id,
        )
        return user_member.status
    except (BadRequest, Forbidden):
        return None


async def handle_dm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle direct messages to the bot for unrestriction flow.

    This handler processes DMs (including /start) and:
    1. Checks if user is a member of the monitored group
    2. Checks if user's profile is complete (photo + username)
    3. If user was restricted by the bot and now has complete profile,
       removes the restriction using the group's default permissions

    Args:
        update: Telegram update containing the message.
        context: Bot context with helper methods.
    """
    # Skip if no message or sender
    if not update.message or not update.message.from_user:
        return

    # Only handle private chats
    if update.effective_chat and update.effective_chat.type != "private":
        return

    user = update.message.from_user
    settings = get_settings()

    # Check user's status in the group
    user_status = await _get_user_status(context, settings.group_id, user.id)

    # User not in group (or we can't check)
    if user_status is None or user_status in ("left", "kicked"):
        await update.message.reply_text(
            "❌ Kamu belum bergabung di grup.\n"
            "Silakan bergabung ke grup terlebih dahulu."
        )
        logger.info(
            f"DM from user {user.id} ({user.full_name}) - not in group {settings.group_id}"
        )
        return

    # Check if user's profile is complete
    result = await check_user_profile(context.bot, user)

    # Profile still incomplete - tell them what's missing
    if not result.is_complete:
        missing = result.get_missing_items()
        missing_text = " dan ".join(missing)
        reply_message = (
            f"❌ Kamu belum memenuhi persyaratan.\n\n"
            f"Mohon lengkapi {missing_text} kamu terlebih dahulu, "
            f"lalu kirim pesan lagi ke bot ini.\n\n"
            f"📖 [Baca aturan grup]({settings.rules_link})"
        )
        await update.message.reply_text(reply_message, parse_mode="Markdown")
        logger.info(
            f"DM from user {user.id} ({user.full_name}) - missing: {missing_text}"
        )
        return

    db = get_database()

    # Check if user was restricted by this bot (not by admin)
    if not db.is_user_restricted_by_bot(user.id, settings.group_id):
        await update.message.reply_text(
            "ℹ️ Kamu tidak memiliki pembatasan dari bot ini.\n"
            "Jika kamu dibatasi oleh admin, silakan hubungi admin grup secara langsung."
        )
        return

    # User was restricted by bot but is no longer restricted on Telegram
    # (e.g., admin already unrestricted them) - just clear our record
    if user_status != "restricted":
        db.mark_user_unrestricted(user.id, settings.group_id)
        await update.message.reply_text(
            "ℹ️ Kamu sudah tidak dibatasi di grup.\n"
            "Silakan bergabung kembali!"
        )
        return

    # Get group's default permissions to restore user to normal state
    chat = await context.bot.get_chat(settings.group_id)
    default_permissions = chat.permissions

    # Remove restriction by applying group's default permissions
    await context.bot.restrict_chat_member(
        chat_id=settings.group_id,
        user_id=user.id,
        permissions=default_permissions,
    )

    # Clear our database record so we don't try to unrestrict again
    db.mark_user_unrestricted(user.id, settings.group_id)

    await update.message.reply_text(
        "✅ Selamat! Kamu sudah memenuhi persyaratan.\n"
        "Pembatasan kamu di grup telah dicabut. Silakan bergabung kembali!"
    )
    logger.info(f"Unrestricted user {user.id} ({user.full_name}) via DM")
