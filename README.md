# Quetie_mbg - Twitch Queue Management Bot

> A production-ready, modular Twitch queue management bot with a secure admin dashboard.

**Version:** 1.0.0  
**Status:** Production-Ready

## Overview

Quetie_mbg is a lightweight but stable Twitch utility bot that manages a link queue system through a dedicated bot account. Viewers submit links in chat using queue commands, and streamers manage the queue through a modern web dashboard.

### Core Features

✅ **Twitch IRC Integration** - Real-time chat monitoring with automatic reconnection  
✅ **Queue Management** - Add, remove, reorder, and play links  
✅ **Link Filtering** - Block domains, keywords, and prevent duplicates  
✅ **Admin Dashboard** - Secure web interface for queue management  
✅ **Persistent Storage** - SQLite (dev) or PostgreSQL (production)  
✅ **JWT Authentication** - Secure admin login and session management  
✅ **24/7 Uptime** - Graceful reconnection and error handling  
✅ **Health Monitoring** - Endpoint for uptime monitoring  

## Quick Start

### Prerequisites

- Python 3.9+
- Twitch bot account (created and added to your channel as moderator)
- Twitch OAuth token with `chat:read:messages` and `chat:edit` scopes

### Installation

```bash
# Clone or download the project
cd Quetie_mbg

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy environment template
copy .env.example .env  # Windows
cp .env.example .env    # macOS/Linux

# Edit .env with your Twitch credentials
# Get OAuth token from: https://twitchapps.com/tokengen/
```

### Configuration

Edit `.env` file:

```env
# Required
TWITCH_BOT_USERNAME=miss_brain_glitch_bot
TWITCH_TARGET_CHANNEL=miss_brain_glitch
TWITCH_OAUTH_TOKEN=oauth:your_token_here

# Security (change in production!)
JWT_SECRET=generate-a-secure-key
ADMIN_USERNAME=admin
```

### Running the Bot

```bash
# Run both bot and web dashboard
python main.py

# Or run bot only
python main.py --mode bot

# Or run web dashboard only
python main.py --mode web

# Initialize database only
python main.py --init-db
```

**Output:**
```
[INFO] Initializing database...
[INFO] Database tables created/verified
[INFO] Starting Twitch IRC Bot...
[INFO] Bot connected to #miss_brain_glitch
[INFO] Starting web server on 0.0.0.0:8000
```

### Web Dashboard

Access the dashboard at: `http://localhost:8000`

**Default Credentials:**
- Username: `admin`
- Password: `admin123` (change immediately!)

## Production Deployment

Quetie_mbg is packaged to run as a single Render web service with the frontend built into the backend container.

### Required environment variables

```env
ENVIRONMENT=production
JWT_SECRET=replace-with-a-long-random-secret
ADMIN_PASSWORD_HASH=precomputed-bcrypt-hash
CORS_ALLOWED_ORIGINS=https://your-app.onrender.com
MAX_QUEUE_SIZE=500
LOG_LEVEL=INFO
```

### Render setup

1. Create a new Render Web Service from this repository.
2. Use `render.yaml` or the Docker deploy option.
3. Set `JWT_SECRET` and `ADMIN_PASSWORD_HASH` as secret values.
4. Keep `ENVIRONMENT=production` so secure cookie and header behavior stays enabled.
5. Point UptimeRobot at `GET /health` for uptime monitoring.

### Docker (local test)

Build and run the production container locally to verify startup and health checks:

```bash
docker build -t quetie_mbg:local .
docker run --env-file .env -p 8000:8000 --name quetie_mbg_local quetie_mbg:local
# then in another terminal
curl http://localhost:8000/health
```

If Docker isn't available locally, use `python main.py --mode all` with a virtualenv.

### Automated local verification scripts

Two helper scripts are provided to simplify local Docker verification:

- `scripts/verify_docker.sh` — Linux/macOS (bash)
- `scripts/verify_docker.ps1` — Windows (PowerShell)

Usage (bash):

```bash
chmod +x scripts/verify_docker.sh
./scripts/verify_docker.sh
```

Usage (PowerShell):

```powershell
.\scripts\verify_docker.ps1
# Optionally: .\scripts\verify_docker.ps1 -Cleanup
```

The scripts perform the following steps:

- Build the Docker image (`quetie_mbg:local`).
- Remove any previous test container named `quetie_mbg_local`.
- Start the container with env vars from `.env` (if present).
- Wait for `/health` to respond (up to 60s).
- Show the `/health` response and tail container logs for debugging.

If the health check fails, the scripts print recent container logs and exit non-zero.


### Quick verification script

Two helper scripts are included to simplify repeated local verification before deploying to Render:

- `scripts/local_verify.sh` — POSIX shell (Linux/macOS)
- `scripts/local_verify.ps1` — PowerShell (Windows)

Usage (Linux/macOS):

```bash
bash scripts/local_verify.sh
```

Usage (Windows PowerShell):

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\local_verify.ps1 -Port 8000
```

The scripts will:

- build the Docker image
- remove old test container if present
- start the container with `--env-file .env` and port mapping
- wait for `/health` to respond (default 60s)
- tail the container logs on success
- exit non-zero with logs if the health check fails

Edit `.env` from `.env.example` to populate runtime secrets before running.


### Runtime behavior

- Frontend builds during the Docker image build and is served by FastAPI from `quetie/web/static`.
- Auth uses JWT login plus a secure session cookie for SSE.
- Mutating API calls require a CSRF token header.
- `/health` is a lightweight unauthenticated health endpoint for Render and external monitors.

## Architecture

### Directory Structure

```
Quetie_mbg/
├── quetie/                    # Main package
│   ├── config/
│   │   └── settings.py        # Configuration management
│   ├── db/
│   │   ├── models.py          # SQLAlchemy models
│   │   └── database.py        # Database initialization
│   ├── filtering/
│   │   ├── validators.py      # Link validation
│   │   └── filters.py         # Filtering engine
│   ├── queue/
│   │   └── manager.py         # Queue management
│   ├── twitch_bot/
│   │   ├── client.py          # IRC client
│   │   └── handlers.py        # Command handlers
│   ├── web/
│   │   ├── app.py             # FastAPI application
│   │   ├── auth.py            # Authentication
│   │   └── static/            # Frontend files
│   └── utils/
│       └── logger.py          # Logging setup
├── tests/                      # Automated tests
├── main.py                     # Entry point
├── requirements.txt            # Python dependencies
├── .env.example               # Configuration template
└── README.md                  # This file
```

### Module Overview

**Config** (`quetie/config/`)
- Environment-based configuration management
- Settings validation for production/development modes

**Database** (`quetie/db/`)
- SQLAlchemy ORM models
- Database initialization and session management
- Models: Admin, QueueEntry, BlockedDomain, BotStatistic

**Filtering** (`quetie/filtering/`)
- URL validation and parsing
- Domain and keyword blocking
- Duplicate detection

**Queue** (`quetie/queue/`)
- Add/remove/reorder queue entries
- Status tracking (pending, playing, completed)
- Search and statistics

**Twitch Bot** (`quetie/twitch_bot/`)
- IRC client with auto-reconnection
- Command parsing and routing
- Message formatting

**Web** (`quetie/web/`)
- FastAPI REST API
- JWT authentication
- Admin dashboard endpoints

## API Endpoints

### Authentication

```
POST   /api/auth/login             - Login with credentials
GET    /api/auth/me                - Get current admin info
```

### Queue Management

```
GET    /api/queue                  - Get queue entries
POST   /api/queue/add              - Add entry to queue
POST   /api/queue/{id}/play        - Mark as playing
POST   /api/queue/{id}/complete    - Mark as completed
DELETE /api/queue/{id}             - Remove from queue
POST   /api/queue/reorder          - Reorder entries
GET    /api/queue/search           - Search queue
GET    /api/queue/stats            - Get statistics
```

### Filters

```
GET    /api/filters/blocked-domains    - Get blocked domains
POST   /api/filters/blocked-domains    - Add blocked domain
DELETE /api/filters/blocked-domains/{d} - Remove blocked domain
GET    /api/filters/blocked-keywords   - Get blocked keywords
```

### Health

```
GET    /health                     - Health check (no auth required)
```

## Twitch Commands

Users in chat can use these commands:

```
!add <url>          - Submit a link to the queue
!queue              - Show next link in queue
!queuesize          - Show queue size
!queuehelp          - Show help information
```

### Example

```
User: !add https://www.example.com/video
Bot: @User Added to queue (position 5)

User: !queue
Bot: Next in queue: https://www.example.com/video (from @User)

User: !queuesize
Bot: Queue size: 5 links waiting
```

## Filtering System

### Default Blocked Types

- Discord invite/server links
- Nightbot and similar bot service links
- Self-promo (Twitch, YouTube, Twitter, etc.)

### Configurable Blocking

Add blocked domains through the admin dashboard:

1. Go to `/dashboard` → "Filters" or "Settings"
2. Add domain or keyword to block list
3. Provide reason (optional)
4. Changes apply immediately

## Database

### Models

**Admin** - Dashboard admin users with roles

**AdminSession** - JWT sessions for admin authentication

**QueueEntry** - Submitted links with status tracking
- Status: pending, playing, completed, removed, blocked
- Tracks submitter, position, and timestamps

**BlockedDomain** - Domains to reject

**BlockedKeyword** - Keywords/patterns to block

**BotStatistic** - Queue statistics and metrics

## Security

### Best Practices

✅ Store secrets in environment variables only  
✅ JWT tokens expire after 24 hours  
✅ Passwords hashed with bcrypt  
✅ All user input validated and sanitized  
✅ Database queries use parameterized statements  
✅ Admin endpoints require authentication  

### Production Setup

1. **Change Secrets:**
   ```bash
   # Generate strong JWT secret
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

2. **Update Admin Password:**
   ```bash
   # Generate password hash
   python -c "import bcrypt; hash = bcrypt.hashpw(b'yourpassword', bcrypt.gensalt()).decode(); print(hash)"
   ```

3. **Use PostgreSQL:**
   ```env
   DATABASE_URL=postgresql://user:password@host:5432/quetie
   ```

4. **Enable HTTPS:** Deploy behind reverse proxy (nginx) with SSL

## Deployment

### Local Development

```bash
# Run with hot-reload
python main.py
```

### Docker

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["python", "main.py"]
```

```bash
docker build -t quetie_mbg .
docker run -p 8000:8000 -e TWITCH_OAUTH_TOKEN=oauth:... quetie_mbg
```

### Render Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed instructions.

### Environment Variables for Production

```bash
# Critical for security
export JWT_SECRET="your-generated-secret"
export ADMIN_USERNAME="your-admin-user"
export ADMIN_PASSWORD_HASH="hashed-password"

# Twitch
export TWITCH_OAUTH_TOKEN="oauth:your-token"
export TWITCH_BOT_USERNAME="your-bot-account"
export TWITCH_TARGET_CHANNEL="your-channel"

# Database (if not SQLite)
export DATABASE_URL="postgresql://..."

# Server
export WEB_HOST="0.0.0.0"
export WEB_PORT="8000"
export ENVIRONMENT="production"
```

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=quetie tests/

# Run specific test file
pytest tests/test_filtering.py -v
```

## Troubleshooting

### Bot Won't Connect

```
[ERROR] Connection failed: [Errno 11001] getaddrinfo failed
```

**Solution:** Check internet connection and Twitch is accessible.

### Invalid OAuth Token

```
[ERROR] Connection failed: Login authentication failed
```

**Solution:** 
1. Get new token from https://twitchapps.com/tokengen/
2. Ensure token has correct scopes: `chat:read:messages`, `chat:edit`
3. Check token in `.env` is correct format

### Admin Login Fails

```
[WARNING] Failed login attempt for admin: admin
```

**Solution:**
1. Verify credentials in `.env`
2. Reset password by deleting database and restarting
3. Default credentials: `admin` / `admin123`

### Database Locked (SQLite)

```
[ERROR] database is locked
```

**Solution:**
1. Stop bot: `Ctrl+C`
2. Delete database: `rm quetie.db`
3. Restart bot to recreate database

## Performance & Scaling

### Single Instance (Default)

- Handles 1000+ queue entries
- Supports 100+ concurrent admin sessions
- Suitable for typical Twitch streams

### Optimization Tips

1. **Use PostgreSQL** for production
2. **Enable pagination** in API queries
3. **Cache filter lists** in memory
4. **Use a CDN** for static assets
5. **Load balance** with multiple instances behind reverse proxy

## Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create feature branch: `git checkout -b feature/my-feature`
3. Commit changes: `git commit -am 'Add feature'`
4. Push to branch: `git push origin feature/my-feature`
5. Submit pull request

## License

MIT License - See LICENSE file for details

## Support & Community

- **Issues:** Report bugs on GitHub Issues
- **Discussions:** Share ideas in GitHub Discussions
- **Documentation:** See docs/ folder for additional guides

## Changelog

### v1.0.0 (Initial Release)

- ✅ Twitch IRC bot integration
- ✅ Queue management system
- ✅ Admin dashboard
- ✅ Link filtering
- ✅ JWT authentication
- ✅ Production-ready architecture
- ✅ Comprehensive tests
- ✅ Documentation and deployment guides

## Roadmap

- [ ] Moderator roles and permissions
- [ ] Advanced queue analytics
- [ ] Custom command creation
- [ ] Queue auto-play with Spotify integration
- [ ] Mobile dashboard app
- [ ] Community features (voting, suggestions)

---

**Built with ❤️ for streamers by streamers**

Made for `miss_brain_glitch` Twitch channel
