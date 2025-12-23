from unittest.mock import AsyncMock, MagicMock

import pytest

from bot.services.bot_info import BotInfoCache


@pytest.fixture(autouse=True)
def reset_cache():
    BotInfoCache.reset()
    yield
    BotInfoCache.reset()


class TestBotInfoCache:
    async def test_fetches_username_on_first_call(self):
        bot = AsyncMock()
        me = MagicMock()
        me.username = "test_bot"
        bot.get_me.return_value = me

        username = await BotInfoCache.get_username(bot)

        assert username == "test_bot"
        bot.get_me.assert_called_once()

    async def test_caches_username_on_subsequent_calls(self):
        bot = AsyncMock()
        me = MagicMock()
        me.username = "test_bot"
        bot.get_me.return_value = me

        await BotInfoCache.get_username(bot)
        await BotInfoCache.get_username(bot)
        await BotInfoCache.get_username(bot)

        bot.get_me.assert_called_once()

    async def test_reset_clears_cache(self):
        bot = AsyncMock()
        me = MagicMock()
        me.username = "test_bot"
        bot.get_me.return_value = me

        await BotInfoCache.get_username(bot)
        BotInfoCache.reset()
        await BotInfoCache.get_username(bot)

        assert bot.get_me.call_count == 2
