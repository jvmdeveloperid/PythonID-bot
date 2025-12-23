# PythonID Group Management Bot

A Telegram bot that monitors group messages and warns users who don't have a public profile picture or username set.

## Features

- Monitors all text messages in a configured group
- Checks if users have a public profile picture
- Checks if users have a username set
- Sends warnings to a dedicated topic (thread) for non-compliant users
- **Warning topic protection**: Only admins and the bot can post in the warning topic
- **DM unrestriction flow**: Restricted users can DM the bot to get unrestricted after completing their profile
- **Progressive restriction**: Optional mode to restrict users after multiple warnings

## Requirements

- Python 3.14+
- [uv](https://docs.astral.sh/uv/) package manager

## Setup

### 1. Create Your Bot

1. Open Telegram and search for [@BotFather](https://t.me/BotFather)
2. Send `/newbot` and follow the prompts
3. Copy the bot token you receive

### 2. Set Up Your Group

1. Create a new group or use an existing one
2. **Enable Topics** in the group:
   - Go to Group Settings → Topics → Enable Topics
3. Create a topic for bot warnings (e.g., "Bot Warnings" or "Profile Alerts")
4. Add your bot to the group as an **Administrator** with these permissions:
   - Read messages
   - Send messages
   - Delete messages (for warning topic protection)
   - Restrict members (for progressive restriction mode)

### 3. Get Group ID

**Option A: Using @userinfobot**
1. Add [@userinfobot](https://t.me/userinfobot) to your group
2. The bot will reply with the group ID (negative number starting with `-100`)
3. Remove the bot after getting the ID

**Option B: Using your bot**
1. Temporarily add this handler to your bot to print chat IDs:
   ```python
   async def debug_handler(update, context):
       print(f"Chat ID: {update.effective_chat.id}")
   ```
2. Send a message in the group and check the console

### 4. Get Topic ID (message_thread_id)

**Option A: From message link**
1. Right-click any message in your warning topic
2. Click "Copy Message Link"
3. The link format is: `https://t.me/c/XXXXXXXXXX/TOPIC_ID/MESSAGE_ID`
4. The `TOPIC_ID` is the number you need (e.g., `123`)

**Option B: From forwarded message**
1. Forward a message from the topic to [@userinfobot](https://t.me/userinfobot)
2. Look for the `message_thread_id` in the response

**Note:** The "General" topic has ID `1`. Custom topics have higher IDs.

### 5. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your values:

```env
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrSTUvwxYZ
GROUP_ID=-1001234567890
WARNING_TOPIC_ID=42
RESTRICT_FAILED_USERS=false
RULES_LINK=https://t.me/yourgroup/rules
```

## Installation

```bash
# Install dependencies
uv sync

# Run the bot (production)
uv run pythonid-bot

# Run the bot (staging)
BOT_ENV=staging uv run pythonid-bot
```

## Environment Configuration

The bot supports multiple environments via the `BOT_ENV` variable:

| BOT_ENV | Config File |
|---------|-------------|
| `production` (default) | `.env` |
| `staging` | `.env.staging` |

```bash
# Production (default)
uv run pythonid-bot

# Staging
BOT_ENV=staging uv run pythonid-bot
```

## Testing

```bash
# Run tests
uv run pytest

# Run tests with coverage
uv run pytest --cov=bot --cov-report=term-missing

# Run tests verbosely
uv run pytest -v
```

### Test Coverage

The project maintains comprehensive test coverage:
- **All modules**: 100% coverage (237/237 statements)
  - Services: `bot_info.py`, `user_checker.py`
  - Handlers: `dm.py`, `message.py`, `topic_guard.py`
  - Database: `service.py`, `models.py`
  - Config: `config.py`

All modules are fully unit tested with:
- Mocked async dependencies (telegram bot API calls)
- Edge case handling (errors, empty results, boundary conditions)
- Database initialization and schema validation
- 81 total tests across 8 test modules

## Project Structure

```
PythonID/
├── pyproject.toml
├── .env                  # Your configuration (not committed)
├── .env.example          # Example configuration
├── README.md
├── data/
│   └── bot.db            # SQLite database (auto-created)
├── tests/
│   ├── test_bot_info.py
│   ├── test_config.py
│   ├── test_database.py
│   ├── test_dm_handler.py
│   ├── test_message_handler.py
│   ├── test_topic_guard.py
│   └── test_user_checker.py
└── src/
    └── bot/
        ├── main.py           # Entry point
        ├── config.py         # Pydantic settings
        ├── handlers/
        │   ├── dm.py         # DM unrestriction handler
        │   ├── message.py    # Group message handler
        │   └── topic_guard.py # Warning topic protection
        ├── database/
        │   ├── models.py     # SQLModel schemas
        │   └── service.py    # Database operations
        └── services/
            ├── bot_info.py   # Bot info caching
            └── user_checker.py  # Profile validation
```

## How It Works

### Group Message Monitoring
1. Bot listens to all text messages in the configured group
2. For each message, it checks if the sender has:
   - A public profile picture (using `get_user_profile_photos`)
   - A username set
3. If either is missing:
   - **Warning mode** (default): Sends a warning to the designated topic
   - **Restrict mode**: Progressive enforcement (see below)

### Progressive Restriction Mode
When `RESTRICT_FAILED_USERS=true`:
1. **First message** → Warning sent to warning topic with DM link
2. **Messages 2 to (N-1)** → Silent (no spam)
3. **Message N** → User restricted, notification sent with DM link

### Warning Topic Protection
- Only group administrators and the bot itself can post in the warning topic
- Messages from regular users are automatically deleted

### DM Unrestriction Flow
When a restricted user DMs the bot (or sends `/start`):
1. Bot checks if user is in the group
2. Bot checks if user now has complete profile (photo + username)
3. If complete and user was restricted by the bot, restriction is lifted
4. If user was restricted by an admin (not the bot), they're told to contact admin

## Configuration Options

| Variable | Description | Default |
|----------|-------------|---------|
| `TELEGRAM_BOT_TOKEN` | Bot token from @BotFather | Required |
| `GROUP_ID` | Group ID to monitor (negative number) | Required |
| `WARNING_TOPIC_ID` | Topic ID for warning messages | Required |
| `RESTRICT_FAILED_USERS` | Enable progressive restriction | `false` |
| `WARNING_THRESHOLD` | Messages before restriction | `3` |
| `DATABASE_PATH` | SQLite database path | `data/bot.db` |
| `RULES_LINK` | Link to group rules message | `https://t.me/pythonID/290029/321799` |

## Troubleshooting

### Bot doesn't respond
- Ensure the bot is added as an admin to the group
- Verify `GROUP_ID` is correct (should be negative, starting with `-100`)
- Check that Topics are enabled in the group

### Warnings not appearing in topic
- Verify `WARNING_TOPIC_ID` is correct
- Make sure the topic exists and hasn't been deleted

### "Chat not found" error
- The bot might not be in the group yet
- The group ID might be incorrect

### Users can't unrestrict via DM
- User must be a member of the group (not left/kicked)
- User must have been restricted by the bot, not by an admin
- User must have completed their profile (photo + username)

## License

MIT
