Quetie_MBG Render MVP Deployment
================================

Local startup
- Install Python 3.12+.
- Run `pip install -r requirements.txt`.
- Copy `.env.example` to `.env`.
- Start the full app with `python main.py --mode all`.
- Open `http://127.0.0.1:8000`.

Required environment variables
- `ENVIRONMENT=production`
- `JWT_SECRET=<strong secret>`
- `ADMIN_USERNAME=<dashboard admin>`
- `ADMIN_PASSWORD_HASH=<bcrypt hash>` or leave empty only for first local boot
- `TWITCH_BOT_USERNAME=<bot account>`
- `TWITCH_TARGET_CHANNEL=<channel name>`
- `TWITCH_OAUTH_TOKEN=oauth:...`
- `PORT` is supplied automatically by Render

Render deployment steps
1. Push the repo to GitHub.
2. Create a new Render Web Service from the repo.
3. Use the included `render.yaml` or set:
   Start command: `python main.py --mode all`
   Build command: `pip install -r requirements.txt`
4. Attach a persistent disk and mount it at `/opt/render/project/src/data`.
5. Confirm `DATABASE_URL=sqlite:///./data/quetie.db`.
6. Add the required environment variables in the Render dashboard.
7. Deploy and confirm `GET /health` returns `healthy`.

24/7 uptime notes
- Keep the service on a plan that supports a persistent disk.
- Use Render health checks against `/health`.
- Optional: add UptimeRobot with a 5-minute HTTPS monitor pointed at `/health`.

Troubleshooting
- Bot not connecting: verify `TWITCH_OAUTH_TOKEN` includes the `oauth:` prefix.
- Queue not surviving restarts: confirm the Render persistent disk is attached and `DATABASE_URL` points into `/data`.
- Dashboard loads but autoplay stalls: check `/api/diagnostics` and confirm only one item is `playing`.
- Embedded page blank: the site likely blocks framing; use the dashboard fallback and manual skip.
- Deployment install failure: verify you are using the updated `requirements.txt`.

Autoplay validation checklist
- Queue a YouTube URL and confirm it advances on end.
- Queue a direct `.mp4` and confirm it advances on end.
- Queue an article URL and confirm it renders or falls back, then advances only when manually skipped.
- Queue an unsupported or broken link and confirm the player fails gracefully and moves on.
- Refresh the dashboard while an item is playing and confirm the current item is restored.
- Restart the service and confirm queue entries and the active item persist.
