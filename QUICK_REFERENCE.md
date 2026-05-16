# Quick Reference - Quetie_mbg

## Project Structure at a Glance

```
Quetie_mbg/
├── quetie/                # Main Python package
│   ├── config/            # Configuration (settings.py)
│   ├── db/                # Database (models, initialization)
│   ├── filtering/         # URL validation & blocking
│   ├── queue/             # Queue management
│   ├── twitch_bot/        # IRC bot client & handlers
│   ├── web/               # FastAPI app & auth
│   │   └── static/        # Frontend dashboard (index.html)
│   └── utils/             # Utilities (logger)
├── tests/                 # Unit tests
├── main.py                # Entry point
├── requirements.txt       # Dependencies
├── .env.example          # Configuration template
├── README.md             # Full documentation
├── SETUP.md              # Setup instructions
└── DEPLOYMENT.md         # Deployment guide
```

## Quick Start Commands

```bash
# Setup
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # macOS/Linux
pip install -r requirements.txt

# Configuration
copy .env.example .env  # Windows
cp .env.example .env    # macOS/Linux
# Edit .env with your Twitch OAuth token

# Run
python main.py          # Run bot + web dashboard
python main.py --mode bot   # Bot only
python main.py --mode web   # Web dashboard only

# Database
python main.py --init-db    # Initialize database

# Testing
pytest               # Run all tests
pytest tests/test_filtering.py -v  # Run specific tests
```

## Environment Variables (Critical)

| Variable | Purpose | Example |
|----------|---------|---------|
| `TWITCH_BOT_USERNAME` | Bot account name | `miss_brain_glitch_bot` |
| `TWITCH_TARGET_CHANNEL` | Channel to monitor | `miss_brain_glitch` |
| `TWITCH_OAUTH_TOKEN` | Bot OAuth token | `oauth:xxxxx` |
| `JWT_SECRET` | Security key | Auto-generated |
| `ADMIN_USERNAME` | Admin login name | `admin` |
| `DATABASE_URL` | Database connection | `sqlite:///./quetie.db` |

## API Endpoints (POST/GET/DELETE)

**Auth:**
- `POST /api/auth/login` - Login
- `GET /api/auth/me` - Current user

**Queue:**
- `GET /api/queue` - Get queue
- `POST /api/queue/add` - Add entry
- `POST /api/queue/{id}/play` - Mark playing
- `DELETE /api/queue/{id}` - Remove entry
- `GET /api/queue/stats` - Statistics

**Health:**
- `GET /health` - Health check

## Twitch Chat Commands

```
!add <url>      Submit link to queue
!queue          Show next link
!queuesize      Show queue size
!queuehelp      Show help
```

## Web Dashboard

- **URL:** `http://localhost:8000`
- **Default Username:** `admin`
- **Default Password:** `admin123`
- **⚠️ Change password on first login!**

## Project Layers

### 1. Twitch Bot (`quetie/twitch_bot/`)
- IRC client with auto-reconnection
- Command parsing (!add, !queue, etc.)
- Real-time chat monitoring

### 2. Queue Management (`quetie/queue/`)
- Add/remove/reorder entries
- Duplicate detection
- Status tracking
- Search functionality

### 3. Filtering (`quetie/filtering/`)
- URL validation
- Domain blocking
- Keyword filtering
- Pattern matching

### 4. Database (`quetie/db/`)
- SQLAlchemy ORM
- Models: Admin, QueueEntry, BlockedDomain
- Support for SQLite (dev) & PostgreSQL (prod)

### 5. Web API (`quetie/web/`)
- FastAPI REST endpoints
- JWT authentication
- Admin dashboard
- CORS support

### 6. Security (`quetie/web/auth.py`)
- Password hashing (bcrypt)
- JWT token management
- Session tracking
- Role-based access

## Debugging

```bash
# Check if bot is connected
# Look for: "[INFO] Bot connected to #miss_brain_glitch"

# Increase logging
export LOG_LEVEL=DEBUG
python main.py

# Test Twitch token
# Should get: [INFO] Connected to Twitch IRC

# Test database
python -c "from quetie.db.database import Database; Database.initialize(); print('OK')"

# View logs in real-time
tail -f quetie_mbg.log  # Linux/macOS
type quetie_mbg.log     # Windows
```

## Production Checklist

- [ ] Generate strong `JWT_SECRET`
- [ ] Change admin password
- [ ] Use PostgreSQL database
- [ ] Set `ENVIRONMENT=production`
- [ ] Enable HTTPS/SSL
- [ ] Set up monitoring (UptimeRobot)
- [ ] Enable backups
- [ ] Configure firewall rules
- [ ] Test bot with moderation
- [ ] Document custom filters

## Database Models

**Admin**
- id, username, password_hash, email, is_super_admin, created_at

**QueueEntry**
- id, url, status (pending/playing/completed/removed), submitter_username, position, notes, created_at, played_at

**BlockedDomain**
- id, domain, reason, is_active, created_by

**BlockedKeyword**
- id, keyword, reason, is_active, is_regex, created_by

**BotStatistic**
- total_links_submitted, total_links_accepted, total_links_rejected, total_links_played

## Common Issues & Fixes

| Issue | Cause | Fix |
|-------|-------|-----|
| Bot won't connect | Invalid token | Get new token from TwitchApps |
| Login fails | Wrong credentials | Use admin/admin123 by default |
| Database locked | SQLite conflict | Delete .db file and restart |
| Port already in use | Another instance running | Kill process or change WEB_PORT |
| CORS errors | API origin mismatch | Check CORS middleware config |

## Performance Tips

- **SQLite:** Good for < 10k entries
- **PostgreSQL:** Recommended for production
- **Caching:** Filter lists cached in memory
- **Pagination:** API supports limit/offset
- **Connection pooling:** Built-in for databases

## Security Best Practices

✅ Never commit `.env` file  
✅ Rotate `JWT_SECRET` periodically  
✅ Use HTTPS in production  
✅ Validate all user input  
✅ Use strong admin password  
✅ Enable 2FA if possible  
✅ Monitor access logs  
✅ Back up database regularly  

## File Sizes Reference

- `main.py` - ~5 KB (entry point)
- `requirements.txt` - ~1 KB
- Database (empty) - ~100 KB
- Bot running memory - ~100-150 MB
- Web app memory - ~50-100 MB

## Links & Resources

- **Twitch Docs:** https://dev.twitch.tv/docs
- **FastAPI:** https://fastapi.tiangolo.com
- **SQLAlchemy:** https://www.sqlalchemy.org
- **GitHub:** https://github.com/yourusername/quetie_mbg
- **Issues:** Report on GitHub Issues

## Contributing

1. Fork the repository
2. Create feature branch: `git checkout -b feature/my-feature`
3. Make changes and test: `pytest`
4. Commit: `git commit -am 'Add feature'`
5. Push: `git push origin feature/my-feature`
6. Pull request

## License

MIT License - See LICENSE file

---

**For detailed guides, see:**
- Setup: `SETUP.md`
- Deployment: `DEPLOYMENT.md`
- Full docs: `README.md`
