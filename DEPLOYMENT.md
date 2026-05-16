# Deployment Guide for Quetie_mbg

Production deployment instructions for Render, Docker, and traditional servers.

## Table of Contents

1. [Render Deployment](#render-deployment-recommended)
2. [Docker Deployment](#docker-deployment)
3. [Traditional Server](#traditional-server)
4. [Environment Variables](#production-environment-variables)
5. [Health Monitoring](#health-monitoring)
6. [Scaling](#scaling)

---

## Render Deployment (Recommended)

Render is a modern, easy cloud platform. Perfect for this bot.

### Step 1: Prepare GitHub Repository

```bash
# Initialize git if not already done
git init
git add .
git commit -m "Initial commit: Quetie_mbg"

# Add to .gitignore (create file if needed)
```

Create `.gitignore`:

```
venv/
__pycache__/
*.pyc
.env
.env.local
quetie.db
*.db
.DS_Store
.vscode/
```

```bash
# Push to GitHub
git remote add origin https://github.com/yourusername/quetie_mbg.git
git branch -M main
git push -u origin main
```

### Step 2: Create Render Account

1. Go to [render.com](https://render.com)
2. Sign up (use GitHub account for easier setup)
3. Create new organization (optional)

### Step 3: Create Web Service

1. Click "New +" → "Web Service"
2. Connect GitHub repository
3. Configure:
   - **Name:** `quetie-mbg` (or your preferred name)
   - **Environment:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python main.py`
   - **Plan:** Free (or Paid for guaranteed uptime)

### Step 4: Set Environment Variables

1. In Render dashboard, go to service settings
2. Click "Environment"
3. Add these variables:

```
ENVIRONMENT=production
TWITCH_BOT_USERNAME=miss_brain_glitch_bot
TWITCH_TARGET_CHANNEL=miss_brain_glitch
TWITCH_OAUTH_TOKEN=oauth:your_token_here
JWT_SECRET=<generate-secure-key>
ADMIN_USERNAME=<your-admin-username>
ADMIN_PASSWORD_HASH=<bcrypt-hashed-password>
DATABASE_URL=postgresql://<user>:<password>@<host>:5432/<dbname>
WEB_HOST=0.0.0.0
WEB_PORT=8000
LOG_LEVEL=INFO
```

### Step 5: Create PostgreSQL Database (Optional)

For production, use PostgreSQL instead of SQLite:

1. In Render, click "New +" → "PostgreSQL"
2. Configure:
   - **Name:** `quetie-db`
   - **Plan:** Free or Paid
3. Copy connection string
4. Add to Web Service environment as `DATABASE_URL`

### Step 6: Deploy

1. Click "Deploy"
2. Monitor logs in real-time
3. Check Status → "Live"

**Your bot is now live!** Visit `https://<your-service>.onrender.com`

### Step 7: Keep Bot Alive (Free Plan)

Render free tier services spin down after 15 minutes of inactivity.

**Option A: UptimeRobot (Recommended)**

1. Go to [uptimerobot.com](https://uptimerobot.com)
2. Sign up (free account)
3. Create Monitor:
   - **Monitor Type:** HTTP(s)
   - **Friendly Name:** `Quetie_mbg Bot`
   - **URL:** `https://<your-service>.onrender.com/health`
   - **Monitoring Interval:** Every 5 minutes
4. Save - bot stays awake!

**Option B: Paid Render Plan**

- Upgrade to Paid plan for guaranteed uptime
- No more spinning down
- 24/7 availability

---

## Docker Deployment

Deploy using Docker containers.

### Step 1: Create Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create non-root user
RUN useradd -m -u 1000 bot && chown -R bot:bot /app
USER bot

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run application
CMD ["python", "main.py"]
```

### Step 2: Create Docker Compose

`docker-compose.yml`:

```yaml
version: '3.8'

services:
  db:
    image: postgres:15-alpine
    container_name: quetie_db
    environment:
      POSTGRES_DB: quetie
      POSTGRES_USER: quetie_user
      POSTGRES_PASSWORD: secure_password_here
    volumes:
      - db_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  web:
    build: .
    container_name: quetie_bot
    depends_on:
      - db
    environment:
      DATABASE_URL: postgresql://quetie_user:secure_password_here@db:5432/quetie
      TWITCH_BOT_USERNAME: miss_brain_glitch_bot
      TWITCH_TARGET_CHANNEL: miss_brain_glitch
      TWITCH_OAUTH_TOKEN: oauth:your_token
      JWT_SECRET: your_secure_jwt_secret
      ADMIN_USERNAME: admin
      ENVIRONMENT: production
    ports:
      - "8000:8000"
    volumes:
      - ./logs:/app/logs

volumes:
  db_data:
```

### Step 3: Build and Run

```bash
# Build Docker image
docker-compose build

# Start services
docker-compose up -d

# View logs
docker-compose logs -f web

# Stop services
docker-compose down

# Remove volumes (WARNING: deletes data)
docker-compose down -v
```

### Step 4: Push to Container Registry

```bash
# Login to Docker Hub
docker login

# Tag image
docker tag quetie_bot yourusername/quetie_mbg:latest

# Push
docker push yourusername/quetie_mbg:latest

# Deploy from Docker Hub on any hosting platform
```

---

## Traditional Server

Deploy on your own VPS or server.

### Step 1: Server Setup

```bash
# SSH into server
ssh user@your-server.com

# Update system
sudo apt-get update
sudo apt-get upgrade -y

# Install Python and dependencies
sudo apt-get install -y python3.11 python3.11-venv python3-pip
sudo apt-get install -y postgresql postgresql-contrib
sudo apt-get install -y nginx supervisor
```

### Step 2: Clone Application

```bash
# Create app directory
sudo mkdir -p /opt/quetie_mbg
cd /opt/quetie_mbg

# Clone from GitHub
git clone https://github.com/yourusername/quetie_mbg.git .

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Step 3: Setup PostgreSQL

```bash
# Connect to PostgreSQL
sudo -u postgres psql

# Create database and user
CREATE DATABASE quetie;
CREATE USER quetie_user WITH PASSWORD 'secure_password';
ALTER ROLE quetie_user SET client_encoding TO 'utf8';
ALTER ROLE quetie_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE quetie_user SET default_transaction_deferrable TO on;
ALTER ROLE quetie_user SET timezone TO 'UTC';
GRANT ALL PRIVILEGES ON DATABASE quetie TO quetie_user;
\q
```

### Step 4: Configure Environment

```bash
# Create .env file
sudo nano /opt/quetie_mbg/.env

# Add production settings
ENVIRONMENT=production
DATABASE_URL=postgresql://quetie_user:secure_password@localhost:5432/quetie
TWITCH_OAUTH_TOKEN=oauth:your_token
JWT_SECRET=your_secure_key
# ... other settings
```

### Step 5: Setup Supervisor

`/etc/supervisor/conf.d/quetie_mbg.conf`:

```ini
[program:quetie_mbg]
directory=/opt/quetie_mbg
command=/opt/quetie_mbg/venv/bin/python main.py
user=www-data
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/quetie_mbg/bot.log
environment=PATH="/opt/quetie_mbg/venv/bin"
```

```bash
# Create log directory
sudo mkdir -p /var/log/quetie_mbg
sudo chown www-data:www-data /var/log/quetie_mbg

# Update supervisor
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start quetie_mbg

# View status
sudo supervisorctl status quetie_mbg
```

### Step 6: Setup Nginx Reverse Proxy

`/etc/nginx/sites-available/quetie_mbg`:

```nginx
upstream quetie_app {
    server 127.0.0.1:8000;
}

server {
    listen 80;
    server_name your-domain.com www.your-domain.com;

    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com www.your-domain.com;

    # SSL certificates (use Let's Encrypt)
    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

    # Security headers
    add_header Strict-Transport-Security "max-age=31536000" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;

    location / {
        proxy_pass http://quetie_app;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /health {
        access_log off;
        proxy_pass http://quetie_app/health;
    }
}
```

```bash
# Enable site
sudo ln -s /etc/nginx/sites-available/quetie_mbg /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx

# Setup SSL with Let's Encrypt
sudo apt-get install -y certbot python3-certbot-nginx
sudo certbot certonly --nginx -d your-domain.com
```

### Step 7: Monitor and Maintain

```bash
# View logs
sudo tail -f /var/log/quetie_mbg/bot.log

# Restart service
sudo supervisorctl restart quetie_mbg

# Check system resources
htop

# Backup database daily
sudo crontab -e
# Add: 0 2 * * * pg_dump quetie > /backups/quetie_$(date +\%Y\%m\%d).sql
```

---

## Production Environment Variables

### Secure Secret Generation

```bash
# Generate JWT secret
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Generate password hash
python -c "import bcrypt; print(bcrypt.hashpw(b'yourpassword', bcrypt.gensalt()).decode())"
```

### Complete Production `.env`

```env
# Environment
ENVIRONMENT=production
LOG_LEVEL=WARNING

# Twitch
TWITCH_BOT_USERNAME=miss_brain_glitch_bot
TWITCH_TARGET_CHANNEL=miss_brain_glitch
TWITCH_OAUTH_TOKEN=oauth:xxxxxxxxxxxxx
TWITCH_CLIENT_ID=xxxxxxxxxxxxx

# Database (PostgreSQL)
DATABASE_URL=postgresql://user:password@host:5432/quetie

# Web Server
WEB_HOST=0.0.0.0
WEB_PORT=8000

# Security
JWT_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
JWT_EXPIRATION_HOURS=24
ADMIN_USERNAME=admin
ADMIN_PASSWORD_HASH=$2b$12$xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Deployment
# (Auto-set by Render/Docker/Server)
```

---

## Health Monitoring

### Endpoint

```
GET /health
```

**Response:**

```json
{
  "status": "healthy",
  "database": true,
  "bot": true,
  "version": "1.0.0"
}
```

### Setup Monitoring

**UptimeRobot:**
1. Monitor: `https://your-service.com/health`
2. Interval: 5 minutes
3. Notify on down

**Datadog:**
```yaml
init_config:
  instances:
    - url: "https://your-service.com/health"
      name: "Quetie_mbg"
      timeout: 5
```

---

## Scaling

### Single Instance (Current Setup)

- Handles 1000+ queue entries
- 100+ concurrent users
- Suitable for most Twitch streams

### Multiple Instances (Future)

```bash
# Load balance with Nginx
upstream quetie_cluster {
    server 127.0.0.1:8001;
    server 127.0.0.1:8002;
    server 127.0.0.1:8003;
}

server {
    listen 80;
    location / {
        proxy_pass http://quetie_cluster;
    }
}
```

### Optimization

1. **Use PostgreSQL** - Better than SQLite for production
2. **Redis caching** - Cache filter lists and frequently accessed data
3. **CDN** - Serve static files from CDN
4. **Database replication** - Master-replica setup for redundancy
5. **Separate bot and web** - Run on separate processes/servers

---

## Troubleshooting Deployment

### Service Won't Start

```bash
# Check logs
journalctl -u quetie_mbg -n 50

# Verify environment variables
env | grep TWITCH

# Test connection
python -c "from main import *; Database.initialize(); print('OK')"
```

### Database Connection Error

```
[ERROR] Error connecting to database

# Solution:
# 1. Verify DATABASE_URL is correct
# 2. Check database server is running
# 3. Verify credentials
# 4. Check firewall/network access
```

### Bot Disconnects

```
[WARNING] No data received, disconnecting...

# Solution:
# 1. Check internet connection
# 2. Verify TWITCH_OAUTH_TOKEN is valid
# 3. Check Twitch API status
# 4. Reduce reconnect backoff in settings
```

### High Memory Usage

```bash
# Monitor memory
free -h

# Solutions:
# 1. Reduce WEB_WORKERS
# 2. Enable database connection pooling
# 3. Clear old queue entries
```

---

## Support & Resources

- **Render Docs:** https://render.com/docs
- **Docker Docs:** https://docs.docker.com
- **PostgreSQL Docs:** https://www.postgresql.org/docs
- **Nginx Docs:** https://nginx.org/en/docs
- **Let's Encrypt:** https://letsencrypt.org

---

**Your bot is production-ready! 🚀**
