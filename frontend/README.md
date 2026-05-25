# Quetie Frontend

Scaffolded React + Vite frontend for the Quetie dashboard.

Development:

```bash
cd frontend
npm install
npm run dev
```

Build into `quetie/web/static` (so FastAPI serves it):

```bash
cd frontend
npm run build
# then start backend
python -m uvicorn quetie.web.app:app --reload
```

Login flow:
- POST `/api/auth/login` returns a JWT token
- Frontend posts token to `/api/auth/session` to set an HttpOnly cookie for SSE
- Dashboard connects to `/api/realtime/stream` using EventSource (cookie-based auth)
