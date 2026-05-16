# Setup Instructions for Quetie_mbg

## Prerequisites

- Windows/macOS/Linux
- Python 3.9 or higher
- Twitch account (for bot account)
- Text editor or IDE (VS Code recommended)

## Step 1: Create Twitch Bot Account

1. Go to [Twitch.tv](https://www.twitch.tv)
2. Create a new account (e.g., `miss_brain_glitch_bot`)
3. Verify email address
4. Log in with bot account
5. Go to your main channel's Creator Dashboard
6. Add bot account as moderator (Moderators tab)

## Step 2: Get OAuth Token

1. Visit [TwitchApps Token Generator](https://twitchapps.com/tokengen/)
2. Click "Connect with Twitch"
3. Log in with your **BOT ACCOUNT** (not your main account)
4. Under "Scopes", select:
   - `chat:read:messages` - Read chat messages
   - `chat:edit` - Send chat messages
5. Click "Generate Token"
6. Copy the token (starts with `oauth:`)
7. Keep this token secure - don't share it!

## Step 3: Clone Project

```bash
# Clone the repository
git clone <repository-url> Quetie_mbg
cd Quetie_mbg

# Or if already downloaded, just navigate to folder
cd Quetie_mbg
```

## Step 4: Setup Python Environment

### Windows

```bash
# Create virtual environment
python -m venv venv

# Activate it
venv\Scripts\activate

# You should see (venv) in your terminal
```

### macOS/Linux

```bash
# Create virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate

# You should see (venv) in your terminal
```

## Step 5: Install Dependencies

```bash
# Upgrade pip first
pip install --upgrade pip

# Install project dependencies
pip install -r requirements.txt

# Verify installation
pip list
```

## Step 6: Configure Environment

```bash
# Copy the example configuration
# Windows
copy .env.example .env

# macOS/Linux
cp .env.example .env

# Open .env in your text editor and fill in values
```

### Edit `.env` with Your Values

```env
# Your bot account name
TWITCH_BOT_USERNAME=miss_brain_glitch_bot

# Your main streaming channel
TWITCH_TARGET_CHANNEL=miss_brain_glitch

# OAuth token you got from step 2 (include "oauth:" prefix)
TWITCH_OAUTH_TOKEN=oauth:your_long_token_here

# For development, keep these as default
JWT_SECRET=dev-secret-key-change-in-production
ADMIN_USERNAME=admin

# Leave ADMIN_PASSWORD_HASH empty for default password "admin123"
ADMIN_PASSWORD_HASH=
```

## Step 7: Initialize Database

```bash
# Create database tables
python main.py --init-db

# Expected output:
# [INFO] Initializing database...
# [INFO] Database tables created/verified
```

## Step 8: Run the Bot

```bash
# Start bot and web dashboard
python main.py

# Expected output shows:
# [INFO] Connecting to irc.chat.twitch.tv:6667...
# [INFO] Connected to Twitch IRC - Channel: #miss_brain_glitch
# [INFO] IRC client started
# [INFO] Starting web server on 0.0.0.0:8000
```

Keep this terminal window open - the bot is running!

## Step 9: Access Dashboard

1. Open web browser
2. Go to `http://localhost:8000`
3. Login with:
   - Username: `admin`
   - Password: `admin123`
4. **⚠️ Change password immediately!**

## Step 10: Test Queue Command

1. Open your Twitch channel chat
2. As a regular user (not bot), type: `!add https://example.com`
3. Bot should respond with confirmation
4. Go to dashboard → Queue to see the entry

## Configuration Reference

| Setting | Default | Purpose |
|---------|---------|---------|
| `TWITCH_BOT_USERNAME` | - | Bot account name |
| `TWITCH_TARGET_CHANNEL` | - | Channel to monitor |
| `TWITCH_OAUTH_TOKEN` | - | Bot OAuth token |
| `WEB_HOST` | 0.0.0.0 | Web server address |
| `WEB_PORT` | 8000 | Web server port |
| `DATABASE_URL` | sqlite:///./quetie.db | Database connection |
| `ENVIRONMENT` | development | dev or production |
| `LOG_LEVEL` | INFO | DEBUG, INFO, WARNING, ERROR |

## Troubleshooting Setup

### "ModuleNotFoundError: No module named 'fastapi'"

**Solution:** Make sure virtual environment is activated and dependencies installed.

```bash
# Verify venv is active (should see (venv) in terminal)
# If not:
# Windows: venv\Scripts\activate
# macOS/Linux: source venv/bin/activate

# Then reinstall:
pip install -r requirements.txt
```

### "TWITCH_OAUTH_TOKEN is required"

**Solution:** Add token to `.env` file.

```env
# Make sure to include "oauth:" prefix
TWITCH_OAUTH_TOKEN=oauth:abcdef...
```

### Bot connects then disconnects

**Solution:** Token might be expired. Get a new one from TwitchApps.

### "Database is locked" error

**Solution:** Another instance is running. Stop all instances and delete `quetie.db`:

```bash
# Stop the bot (Ctrl+C in terminal)
# Then delete database
rm quetie.db  # macOS/Linux
del quetie.db # Windows

# Restart:
python main.py --init-db
python main.py
```

## Next Steps

1. ✅ Bot is running - test commands in chat
2. ✅ Access dashboard at http://localhost:8000
3. 📚 Read full documentation in README.md
4. 🚀 Deploy to production (see DEPLOYMENT.md)
5. ⚙️ Customize filters and blocked domains
6. 👥 Create moderator accounts for your team

## Commands Reference

### Bot Commands (in Twitch chat)

```
!add <url>        - Submit link to queue
!queue            - Show next link
!queuesize        - Show queue size
!queuehelp        - Show help
```

### Admin Commands (CLI)

```bash
# Run bot only (no web)
python main.py --mode bot

# Run web only (no bot)
python main.py --mode web

# Run both (default)
python main.py

# Show version
python main.py --version

# Initialize fresh database
python main.py --init-db
```

## Performance Tips

1. **Use PostgreSQL for production** - SQLite for development only
2. **Set `WEB_WORKERS` based on CPU** - Default is 4
3. **Monitor logs** - Check for errors regularly
4. **Back up database** - Regular backups protect data

## Getting Help

1. Check README.md for detailed documentation
2. Review DEPLOYMENT.md for hosting options
3. Check logs in terminal for error messages
4. Verify .env file has correct values
5. Test with `--init-db` to reset everything

---

**You're all set! Your Twitch queue bot is ready to go live! 🎉**
