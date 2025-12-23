"""
Tests for the scheduler service.

Tests the auto-restriction job and scheduler initialization.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from apscheduler.schedulers.background import BackgroundScheduler

from bot.database.models import UserWarning
from bot.services.scheduler import (
    _auto_restrict_sync_wrapper,
    auto_restrict_expired_warnings,
    start_scheduler,
)


class TestAutoRestrictExpiredWarnings:
    @pytest.mark.asyncio
    async def test_restricts_expired_warnings(self):
        """Test that expired warnings are restricted."""
        # Mock database with expired warning
        mock_warning = UserWarning(
            id=1,
            user_id=123,
            group_id=-100999,
            message_count=1,
            first_warned_at=datetime.now(UTC) - timedelta(hours=4),
            last_message_at=datetime.now(UTC),
            is_restricted=False,
            restricted_by_bot=False,
        )

        mock_db = MagicMock()
        mock_db.get_warnings_past_time_threshold.return_value = [mock_warning]
        mock_db.mark_user_restricted = MagicMock()

        # Mock bot
        mock_bot = AsyncMock()
        mock_bot.restrict_chat_member = AsyncMock()
        mock_bot.send_message = AsyncMock()

        # Mock application
        mock_application = MagicMock()
        mock_application.bot = mock_bot

        # Mock settings
        mock_settings = MagicMock()
        mock_settings.warning_time_threshold_minutes = 180
        mock_settings.group_id = -100999
        mock_settings.warning_topic_id = 123
        mock_settings.rules_link = "https://example.com/rules"

        with patch("bot.services.scheduler.get_database", return_value=mock_db):
            with patch("bot.services.scheduler.get_settings", return_value=mock_settings):
                with patch(
                    "bot.services.scheduler.BotInfoCache.get_username",
                    new_callable=AsyncMock,
                    return_value="test_bot",
                ):
                    await auto_restrict_expired_warnings(mock_application)

        # Verify restriction was applied
        mock_bot.restrict_chat_member.assert_called_once()
        call_args = mock_bot.restrict_chat_member.call_args
        assert call_args.kwargs["chat_id"] == -100999
        assert call_args.kwargs["user_id"] == 123

        # Verify database was updated
        mock_db.mark_user_restricted.assert_called_once_with(123, -100999)

        # Verify notification was sent
        mock_bot.send_message.assert_called_once()
        call_args = mock_bot.send_message.call_args
        assert call_args.kwargs["chat_id"] == -100999
        assert call_args.kwargs["message_thread_id"] == 123
        assert "dibatasi" in call_args.kwargs["text"]

    @pytest.mark.asyncio
    async def test_handles_no_expired_warnings(self):
        """Test that function handles empty list gracefully."""
        mock_db = MagicMock()
        mock_db.get_warnings_past_time_threshold.return_value = []

        mock_bot = AsyncMock()
        mock_application = MagicMock()
        mock_application.bot = mock_bot

        mock_settings = MagicMock()
        mock_settings.warning_time_threshold_hours = 3

        with patch("bot.services.scheduler.get_database", return_value=mock_db):
            with patch("bot.services.scheduler.get_settings", return_value=mock_settings):
                await auto_restrict_expired_warnings(mock_application)

        # Should not call restrict or send message
        mock_bot.restrict_chat_member.assert_not_called()
        mock_bot.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_restricts_multiple_expired_warnings(self):
        """Test that multiple expired warnings are processed."""
        mock_warnings = [
            UserWarning(
                id=1,
                user_id=123,
                group_id=-100999,
                message_count=1,
                first_warned_at=datetime.now(UTC) - timedelta(hours=4),
                last_message_at=datetime.now(UTC),
                is_restricted=False,
                restricted_by_bot=False,
            ),
            UserWarning(
                id=2,
                user_id=456,
                group_id=-100999,
                message_count=1,
                first_warned_at=datetime.now(UTC) - timedelta(hours=5),
                last_message_at=datetime.now(UTC),
                is_restricted=False,
                restricted_by_bot=False,
            ),
        ]

        mock_db = MagicMock()
        mock_db.get_warnings_past_time_threshold.return_value = mock_warnings
        mock_db.mark_user_restricted = MagicMock()

        mock_bot = AsyncMock()
        mock_bot.restrict_chat_member = AsyncMock()
        mock_bot.send_message = AsyncMock()

        mock_application = MagicMock()
        mock_application.bot = mock_bot

        mock_settings = MagicMock()
        mock_settings.warning_time_threshold_minutes = 180
        mock_settings.group_id = -100999
        mock_settings.warning_topic_id = 123
        mock_settings.rules_link = "https://example.com/rules"

        with patch("bot.services.scheduler.get_database", return_value=mock_db):
            with patch("bot.services.scheduler.get_settings", return_value=mock_settings):
                with patch(
                    "bot.services.scheduler.BotInfoCache.get_username",
                    new_callable=AsyncMock,
                    return_value="test_bot",
                ):
                    await auto_restrict_expired_warnings(mock_application)

        # Verify both users were restricted
        assert mock_bot.restrict_chat_member.call_count == 2
        assert mock_db.mark_user_restricted.call_count == 2
        assert mock_bot.send_message.call_count == 2

    @pytest.mark.asyncio
    async def test_handles_restriction_errors(self):
        """Test that function handles errors gracefully."""
        mock_warning = UserWarning(
            id=1,
            user_id=123,
            group_id=-100999,
            message_count=1,
            first_warned_at=datetime.now(UTC) - timedelta(hours=4),
            last_message_at=datetime.now(UTC),
            is_restricted=False,
            restricted_by_bot=False,
        )

        mock_db = MagicMock()
        mock_db.get_warnings_past_time_threshold.return_value = [mock_warning]

        mock_bot = AsyncMock()
        mock_bot.restrict_chat_member = AsyncMock(side_effect=Exception("API error"))

        mock_application = MagicMock()
        mock_application.bot = mock_bot

        mock_settings = MagicMock()
        mock_settings.warning_time_threshold_minutes = 180
        mock_settings.group_id = -100999

        with patch("bot.services.scheduler.get_database", return_value=mock_db):
            with patch("bot.services.scheduler.get_settings", return_value=mock_settings):
                # Should not raise, but log the error
                await auto_restrict_expired_warnings(mock_application)

        # Verify restriction was attempted
        mock_bot.restrict_chat_member.assert_called_once()

    @pytest.mark.asyncio
    async def test_uses_correct_time_threshold(self):
        """Test that the correct time threshold from settings is used."""
        mock_db = MagicMock()
        mock_db.get_warnings_past_time_threshold.return_value = []

        mock_bot = AsyncMock()
        mock_application = MagicMock()
        mock_application.bot = mock_bot

        mock_settings = MagicMock()
        mock_settings.warning_time_threshold_minutes = 300  # Different threshold (5 hours)

        with patch("bot.services.scheduler.get_database", return_value=mock_db):
            with patch("bot.services.scheduler.get_settings", return_value=mock_settings):
                await auto_restrict_expired_warnings(mock_application)

        # Verify correct threshold was passed to database query
        mock_db.get_warnings_past_time_threshold.assert_called_once_with(300)


class TestAutoRestrictSyncWrapper:
    def test_wrapper_executes_async_function(self):
        """Test that sync wrapper properly executes the async function."""
        mock_warning = UserWarning(
            id=1,
            user_id=123,
            group_id=-100999,
            message_count=1,
            first_warned_at=datetime.now(UTC) - timedelta(minutes=200),
            last_message_at=datetime.now(UTC),
            is_restricted=False,
            restricted_by_bot=False,
        )

        mock_db = MagicMock()
        mock_db.get_warnings_past_time_threshold.return_value = [mock_warning]
        mock_db.mark_user_restricted = MagicMock()

        mock_bot = AsyncMock()
        mock_bot.restrict_chat_member = AsyncMock()
        mock_bot.send_message = AsyncMock()

        mock_application = MagicMock()
        mock_application.bot = mock_bot

        mock_settings = MagicMock()
        mock_settings.warning_time_threshold_minutes = 180
        mock_settings.group_id = -100999
        mock_settings.warning_topic_id = 123
        mock_settings.rules_link = "https://example.com/rules"

        with patch("bot.services.scheduler.get_database", return_value=mock_db):
            with patch("bot.services.scheduler.get_settings", return_value=mock_settings):
                with patch(
                    "bot.services.scheduler.BotInfoCache.get_username",
                    new_callable=AsyncMock,
                    return_value="test_bot",
                ):
                    # Call the sync wrapper
                    _auto_restrict_sync_wrapper(mock_application)

        # Verify the async function was executed
        mock_bot.restrict_chat_member.assert_called_once()
        mock_db.mark_user_restricted.assert_called_once()
        mock_bot.send_message.assert_called_once()


class TestStartScheduler:
    def test_creates_scheduler(self):
        """Test that scheduler is created and started."""
        mock_application = MagicMock()

        scheduler = start_scheduler(mock_application)

        assert scheduler is not None
        assert isinstance(scheduler, BackgroundScheduler)
        assert scheduler.running is True

        # Clean up
        scheduler.shutdown()

    def test_adds_auto_restrict_job(self):
        """Test that auto-restriction job is registered."""
        mock_application = MagicMock()

        scheduler = start_scheduler(mock_application)

        # Get the job
        jobs = scheduler.get_jobs()
        assert len(jobs) == 1

        job = jobs[0]
        assert job.id == "auto_restrict_job"
        assert "auto-restrict" in job.name.lower() or "auto_restrict" in job.name.lower()

        # Clean up
        scheduler.shutdown()

    def test_scheduler_interval_is_5_minutes(self):
        """Test that job runs every 5 minutes."""
        mock_application = MagicMock()

        scheduler = start_scheduler(mock_application)

        job = scheduler.get_jobs()[0]
        # APScheduler interval trigger should be 5 minutes
        assert job.trigger.interval.total_seconds() == 300  # 5 minutes * 60 seconds

        # Clean up
        scheduler.shutdown()
