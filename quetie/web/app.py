"""
FastAPI web application for Quetie_mbg.
"""

from __future__ import annotations

import asyncio
import ipaddress
import json
import socket
import time
from contextlib import asynccontextmanager
from datetime import timedelta
from pathlib import Path
from threading import Lock
from typing import List, Optional
from urllib.parse import urlparse, urljoin, quote, unquote

import httpx
from bs4 import BeautifulSoup
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, Response, StreamingResponse
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from quetie.config.settings import settings
from quetie.db.database import Database
from quetie.db.models import Admin, AppSetting, PasswordResetToken
from quetie.filtering.filters import filter_engine
from quetie.queue.manager import queue_manager
from quetie.runtime import runtime_state
from quetie.utils.diagnostics import diagnostics_buffer, record_diagnostic
from quetie.utils.logger import setup_logger
from quetie.utils.time import utc_now
from quetie.web.auth import SecurityManager

logger = setup_logger(__name__)

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
INDEX_PATH = STATIC_DIR / "index.html"

DEFAULT_APP_SETTINGS = {
    "max_queue_size": settings.MAX_QUEUE_SIZE,
    "moderation_enabled": True,
    "upload_limit_mb": 100,
    "autoplay_enabled": False,
    "autoplay_timeout_seconds": 30,
    "preferred_theme": "light",
    "sidebar_collapsed_default": False,
    "proxied_page_allowlist": [],
}

EMBED_SETTINGS = {
    "embed_timeout_seconds": 8,
    "embed_max_response_bytes": 2 * 1024 * 1024,
    "embed_rate_limit_per_minute": 30,
    "embed_rate_limit_cooldown": 60,
}

_rate_limiter = {}
_rate_limiter_lock = Lock()

# Simple in-memory cache for readable views to reduce repeated fetches.
# Keyed by URL; stores tuple (ts, html). TTL in seconds.
_READABLE_CACHE: dict = {}
_READABLE_CACHE_TTL = 300  # 5 minutes


def _readable_cache_get(url: str) -> Optional[str]:
    try:
        rec = _READABLE_CACHE.get(url)
        if not rec:
            return None
        ts, html = rec
        if int(time.time()) - int(ts) > _READABLE_CACHE_TTL:
            # stale
            del _READABLE_CACHE[url]
            return None
        return html
    except Exception:
        return None


def _readable_cache_set(url: str, html: str) -> None:
    try:
        _READABLE_CACHE[url] = (int(time.time()), html)
    except Exception:
        pass


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    success: bool
    token: Optional[str] = None
    message: str = ""


class QueueEntryRequest(BaseModel):
    url: str
    submitter_username: str
    notes: Optional[str] = None


class BlockedDomainRequest(BaseModel):
    domain: str
    reason: Optional[str] = None


class BlockedKeywordRequest(BaseModel):
    keyword: str
    reason: Optional[str] = None
    is_regex: bool = False


class AppSettingsUpdateRequest(BaseModel):
    max_queue_size: Optional[int] = None
    moderation_enabled: Optional[bool] = None
    upload_limit_mb: Optional[int] = None
    autoplay_enabled: Optional[bool] = None
    autoplay_timeout_seconds: Optional[int] = None
    preferred_theme: Optional[str] = None
    sidebar_collapsed_default: Optional[bool] = None


class PasswordResetRequestData(BaseModel):
    username: str


class PasswordResetData(BaseModel):
    token: str
    new_password: str


class AdminCreateRequest(BaseModel):
    username: str
    password: str
    email: Optional[str] = None
    is_super_admin: bool = False


class AdminUpdateRequest(BaseModel):
    email: Optional[str] = None
    password: Optional[str] = None
    is_active: Optional[bool] = None
    is_super_admin: Optional[bool] = None


class EmbedCheckRequest(BaseModel):
    url: str


class EmbedCheckResponse(BaseModel):
    url: str
    status_code: int
    embeddable: bool
    x_frame_options: Optional[str] = None
    content_security_policy: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    database: bool
    bot: bool
    version: str
    runtime: dict


@asynccontextmanager
async def lifespan(_: FastAPI):
    if not Database.is_initialized():
        Database.initialize()
        SecurityManager.init_default_admin()
    filter_engine.refresh_filters()
    queue_manager.restore_runtime_state()
    runtime_state.mark_startup_completed()
    record_diagnostic("app", "startup_completed")
    yield


app = FastAPI(
    title="Quetie_mbg API",
    description="Twitch Queue Management Bot API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _serialize_setting_value(value) -> str:
    return json.dumps(value)


def _load_persistent_settings() -> dict:
    merged = dict(DEFAULT_APP_SETTINGS)
    try:
        with Database.session_context() as session:
            rows = session.query(AppSetting).all()
            for row in rows:
                try:
                    merged[row.key] = json.loads(row.value)
                except Exception:
                    merged[row.key] = row.value
    except Exception as exc:
        logger.error("settings_load_failed error=%s", exc)
        record_diagnostic("settings", "load_failed", level="ERROR", error=str(exc))
    return merged


def _upsert_app_settings(payload: dict) -> dict:
    with Database.session_context() as session:
        for key, value in payload.items():
            row = session.query(AppSetting).filter(AppSetting.key == key).first()
            if row:
                row.value = _serialize_setting_value(value)
            else:
                session.add(AppSetting(key=key, value=_serialize_setting_value(value)))
        session.commit()
    record_diagnostic("settings", "updated", keys=sorted(payload.keys()))
    return _load_persistent_settings()


def _is_valid_admin_username(username: str) -> bool:
    return bool(username and username.strip())


def _runtime_settings_for_embed() -> dict:
    merged = dict(EMBED_SETTINGS)
    persisted = _load_persistent_settings()
    for key in EMBED_SETTINGS:
        if key in persisted:
            merged[key] = persisted[key]
    # include domain allowlist for proxied pages
    if "proxied_page_allowlist" in persisted:
        merged["proxied_page_allowlist"] = persisted["proxied_page_allowlist"]
    return merged


def get_current_admin(authorization: str = Header(None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization header",
        )

    admin = SecurityManager.get_admin_from_token(authorization[7:])
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    return admin


def require_super_admin(admin: dict = Depends(get_current_admin)) -> dict:
    if not admin.get("is_super_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin access required",
        )
    return admin


def _extract_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _is_private_ip(ip_str: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_str)
        return ip.is_private or ip.is_loopback or ip.is_reserved or ip.is_link_local
    except Exception:
        return False


async def _resolve_host_ips(host: str) -> List[str]:
    loop = asyncio.get_running_loop()
    try:
        infos = await loop.run_in_executor(None, lambda: socket.getaddrinfo(host, None))
        return list(dict.fromkeys(info[4][0] for info in infos))
    except Exception:
        return []


def _rate_limit_check(client_ip: str, runtime_config: dict) -> None:
    now = int(time.time())
    per_minute = int(runtime_config.get("embed_rate_limit_per_minute", 30))
    cooldown = int(runtime_config.get("embed_rate_limit_cooldown", 60))

    with _rate_limiter_lock:
        rec = _rate_limiter.get(client_ip, {"count": 0, "ts": now, "cool_until": 0})
        if rec["cool_until"] > now:
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
        if now - rec["ts"] >= 60:
            rec = {"count": 0, "ts": now, "cool_until": 0}
        rec["count"] += 1
        if rec["count"] > per_minute:
            rec["cool_until"] = now + cooldown
            _rate_limiter[client_ip] = rec
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
        _rate_limiter[client_ip] = rec


def _validate_external_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise HTTPException(status_code=400, detail="Only http/https URLs are supported")
    if not parsed.netloc:
        raise HTTPException(status_code=400, detail="Invalid URL")
    return url


async def _guard_external_fetch(request: Request, url: str) -> dict:
    runtime_config = _runtime_settings_for_embed()
    client_ip = _extract_client_ip(request)
    _rate_limit_check(client_ip, runtime_config)

    parsed = urlparse(_validate_external_url(url))
    host = parsed.hostname or ""
    if host in {"localhost"}:
        raise HTTPException(status_code=400, detail="Localhost targets are not allowed")

    resolved_ips = await _resolve_host_ips(host)
    if any(_is_private_ip(ip) for ip in resolved_ips):
        raise HTTPException(status_code=400, detail="Private network targets are not allowed")

    return runtime_config


def _detect_content_type(url: str) -> dict:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    path = parsed.path.lower()

    if "youtube.com" in host or "youtu.be" in host:
        return {"type": "youtube", "viewer_priority": ["native", "external"], "playable": True}
    if "vimeo.com" in host:
        return {"type": "vimeo", "viewer_priority": ["native", "external"], "playable": True}
    if "twitch.tv" in host and ("/videos/" in path or "/clip/" in path):
        return {"type": "twitch_video", "viewer_priority": ["native", "external"], "playable": True}
    if path.endswith((".mp4", ".webm", ".ogg", ".mov", ".m4v", ".avi", ".mkv")):
        return {"type": "direct_video", "viewer_priority": ["native"], "playable": True}
    if path.endswith((".mp3", ".wav", ".aac", ".ogg", ".m4a", ".flac")):
        return {"type": "direct_audio", "viewer_priority": ["native"], "playable": True}
    if parsed.scheme in {"http", "https"}:
        return {"type": "webpage", "viewer_priority": ["proxy", "readability", "external"], "playable": False}
    return {"type": "unsupported", "viewer_priority": ["external"], "playable": False}


def _sanitize_html(html: str) -> str:
    try:
        soup = BeautifulSoup(html, "html.parser")
    except Exception:
        return html

    for tag in soup(["script", "style", "iframe", "noscript", "form", "input", "button"]):
        tag.decompose()

    for element in soup.find_all(True):
        attrs = dict(element.attrs)
        for attr, raw_value in attrs.items():
            value = " ".join(raw_value) if isinstance(raw_value, list) else str(raw_value)
            if attr.lower().startswith("on"):
                del element.attrs[attr]
            elif attr.lower() in {"srcdoc", "formaction", "action"}:
                del element.attrs[attr]
            elif "javascript:" in value.lower():
                del element.attrs[attr]

    return str(soup)


def _extract_readable_content(html: str, url: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    title = (soup.title.string.strip() if soup.title and soup.title.string else url)

    container = soup.find("article")
    if container is None:
        container = max(
            soup.find_all(["main", "section", "div"], recursive=True),
            key=lambda node: len(node.get_text(" ", strip=True)),
            default=soup.body or soup,
        )

    content_html = _sanitize_html(str(container))
    return f"""
    <html>
      <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{title}</title>
      </head>
      <body style="margin:0;font-family:Segoe UI,Arial,sans-serif;background:#f6f7fb;color:#1a202c;">
        <main style="max-width:860px;margin:0 auto;padding:24px 18px 40px;">
          <header style="margin-bottom:20px;">
            <div style="font-size:12px;color:#64748b;text-transform:uppercase;letter-spacing:0.08em;">Readable View</div>
            <h1 style="margin:8px 0 0;font-size:28px;line-height:1.2;">{title}</h1>
            <p style="margin-top:10px;color:#475569;">Original URL: <a href="{url}" target="_blank" rel="noreferrer">{url}</a></p>
          </header>
          <article style="background:white;border-radius:16px;padding:24px;box-shadow:0 8px 24px rgba(15,23,42,0.08);line-height:1.7;">
            {content_html}
          </article>
          <footer style="margin-top:18px;color:#64748b;font-size:14px;">Proxied readable view. Some formatting may differ from the original site.</footer>
        </main>
      </body>
    </html>
    """


async def _fetch_text_response(url: str, timeout_seconds: int, max_bytes: int) -> tuple[str, httpx.Response]:
    async with httpx.AsyncClient(follow_redirects=True, timeout=timeout_seconds) as client:
        response = await client.get(url)
        response.raise_for_status()
        body = response.text
        if len(body.encode("utf-8", errors="ignore")) > max_bytes:
            body = body.encode("utf-8", errors="ignore")[:max_bytes].decode("utf-8", errors="ignore")
        return body, response


@app.get("/health", response_model=HealthResponse, tags=["health"])
async def health_check() -> HealthResponse:
    database_ok = Database.health_check()
    runtime = runtime_state.snapshot()
    return HealthResponse(
        status="healthy" if database_ok else "degraded",
        database=database_ok,
        bot=bool(runtime.get("bot_connected")),
        version="1.0.0",
        runtime=runtime,
    )


@app.post("/api/auth/login", response_model=LoginResponse, tags=["auth"])
async def login(request: LoginRequest) -> LoginResponse:
    success, token, _ = SecurityManager.authenticate_admin(request.username, request.password)
    if not success:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    record_diagnostic("auth", "login_success", username=request.username)
    return LoginResponse(success=True, token=token, message="Login successful")


@app.get("/api/auth/me", tags=["auth"])
async def get_current_user(admin: dict = Depends(get_current_admin)) -> dict:
    return admin


@app.post("/api/auth/request-reset", tags=["auth"])
async def request_password_reset(request: PasswordResetRequestData) -> dict:
    import secrets

    with Database.session_context() as session:
        admin = session.query(Admin).filter(Admin.username == request.username).first()
        if not admin:
            return {"success": True, "message": "If account exists, reset email will be sent"}

        token = secrets.token_urlsafe(32)
        reset_token = PasswordResetToken(
            admin_id=admin.id,
            token=token,
            expires_at=utc_now() + timedelta(hours=1),
        )
        session.add(reset_token)
        session.commit()

    return {"success": True, "message": "Password reset token generated", "token": token}


@app.post("/api/auth/reset-password", tags=["auth"])
async def reset_password(request: PasswordResetData) -> dict:
    if len(request.new_password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

    with Database.session_context() as session:
        token = session.query(PasswordResetToken).filter(PasswordResetToken.token == request.token).first()
        if not token or not token.is_valid():
            raise HTTPException(status_code=400, detail="Invalid or expired reset token")

        token.admin.password_hash = SecurityManager.hash_password(request.new_password)
        token.used = True
        session.commit()
    return {"success": True, "message": "Password reset successfully. You can now login."}


@app.get("/api/admins", tags=["admins"])
async def list_admins(admin: dict = Depends(require_super_admin)) -> dict:
    with Database.session_context() as session:
        admins = session.query(Admin).order_by(Admin.is_super_admin.desc(), Admin.created_at.asc()).all()
        return {"admins": [item.to_dict() for item in admins], "count": len(admins)}


@app.post("/api/admins", tags=["admins"])
async def create_admin(request: AdminCreateRequest, admin: dict = Depends(require_super_admin)) -> dict:
    username = request.username.strip()
    if not _is_valid_admin_username(username):
        raise HTTPException(status_code=400, detail="Username is required")
    if not request.password or len(request.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

    with Database.session_context() as session:
        if session.query(Admin).filter(Admin.username == username).first():
            raise HTTPException(status_code=400, detail="Username already exists")
        if request.email and session.query(Admin).filter(Admin.email == request.email).first():
            raise HTTPException(status_code=400, detail="Email already exists")

        new_admin = Admin(
            username=username,
            email=request.email.strip() if request.email else None,
            password_hash=SecurityManager.hash_password(request.password),
            is_active=True,
            is_super_admin=bool(request.is_super_admin),
        )
        session.add(new_admin)
        session.commit()
        session.refresh(new_admin)
        return {"success": True, "message": f"Access granted to {new_admin.username}", "admin": new_admin.to_dict()}


@app.patch("/api/admins/{admin_id}", tags=["admins"])
async def update_admin(admin_id: int, request: AdminUpdateRequest, admin: dict = Depends(require_super_admin)) -> dict:
    with Database.session_context() as session:
        target = session.query(Admin).filter(Admin.id == admin_id).first()
        if not target:
            raise HTTPException(status_code=404, detail="Admin not found")

        if request.email is not None:
            email = request.email.strip() or None
            if email and session.query(Admin).filter(Admin.email == email, Admin.id != admin_id).first():
                raise HTTPException(status_code=400, detail="Email already exists")
            target.email = email
        if request.password:
            if len(request.password) < 6:
                raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
            target.password_hash = SecurityManager.hash_password(request.password)
        if request.is_active is not None:
            target.is_active = request.is_active
        if request.is_super_admin is not None:
            target.is_super_admin = request.is_super_admin

        session.commit()
        session.refresh(target)
        return {"success": True, "message": f"Admin updated: {target.username}", "admin": target.to_dict()}


@app.get("/api/admins/{admin_id}", tags=["admins"])
async def get_admin_details(admin_id: int, admin: dict = Depends(require_super_admin)) -> dict:
    with Database.session_context() as session:
        target = session.query(Admin).filter(Admin.id == admin_id).first()
        if not target:
            raise HTTPException(status_code=404, detail="Admin not found")
        return {
            "success": True,
            "admin": {
                "id": target.id,
                "username": target.username,
                "email": target.email,
                "password_hash": target.password_hash,
                "is_active": target.is_active,
                "is_super_admin": target.is_super_admin,
                "created_at": target.created_at.isoformat() if target.created_at else None,
                "updated_at": target.updated_at.isoformat() if target.updated_at else None,
            },
        }


@app.delete("/api/admins/{admin_id}", tags=["admins"])
async def remove_admin_access(admin_id: int, admin: dict = Depends(require_super_admin)) -> dict:
    if admin_id == admin["id"]:
        raise HTTPException(status_code=400, detail="You cannot deactivate your own account")
    with Database.session_context() as session:
        target = session.query(Admin).filter(Admin.id == admin_id).first()
        if not target:
            raise HTTPException(status_code=404, detail="Admin not found")
        target.is_active = False
        session.commit()
        return {"success": True, "message": f"Access revoked for {target.username}"}


@app.delete("/api/admins/{admin_id}/permanent", tags=["admins"])
async def permanently_delete_admin(admin_id: int, admin: dict = Depends(require_super_admin)) -> dict:
    if admin_id == admin["id"]:
        raise HTTPException(status_code=400, detail="You cannot delete your own account")
    with Database.session_context() as session:
        target = session.query(Admin).filter(Admin.id == admin_id).first()
        if not target:
            raise HTTPException(status_code=404, detail="Admin not found")
        username = target.username
        session.delete(target)
        session.commit()
        return {"success": True, "message": f"User permanently deleted: {username}"}


@app.get("/api/queue", tags=["queue"])
async def get_queue(skip: int = 0, limit: int = 50, admin: dict = Depends(get_current_admin)) -> dict:
    entries, total = queue_manager.get_queue(limit=limit, offset=skip)
    return {"entries": entries, "total": total, "skip": skip, "limit": limit}


@app.post("/api/queue/add", tags=["queue"])
async def add_to_queue(request: QueueEntryRequest, admin: dict = Depends(get_current_admin)) -> dict:
    success, message, entry_id = queue_manager.add_to_queue(
        url=request.url,
        submitter_username=request.submitter_username,
        notes=request.notes,
    )
    if not success:
        raise HTTPException(status_code=400, detail=message)
    return {"success": True, "message": message, "entry_id": entry_id}


@app.post("/api/queue/{entry_id}/play", tags=["queue"])
async def mark_playing(entry_id: int, open_in_browser: bool = False, admin: dict = Depends(get_current_admin)) -> dict:
    success, message, _ = queue_manager.mark_as_playing(entry_id)
    if not success:
        raise HTTPException(status_code=404, detail=message)
    if open_in_browser:
        logger.info("open_in_browser_ignored entry_id=%s", entry_id)
    return {"success": True, "message": message, "playback_state": queue_manager.get_playback_state()}


@app.get("/api/queue/current", tags=["queue"])
async def get_current_playing(admin: dict = Depends(get_current_admin)) -> dict:
    return {
        "entry": queue_manager.get_current_playing(),
        "playback_state": queue_manager.get_playback_state(),
    }


@app.post("/api/queue/{entry_id}/complete", tags=["queue"])
async def mark_completed(entry_id: int, admin: dict = Depends(get_current_admin)) -> dict:
    success, message = queue_manager.mark_as_completed(entry_id)
    if not success:
        raise HTTPException(status_code=404, detail=message)
    return {"success": True, "message": message, "playback_state": queue_manager.get_playback_state()}


@app.delete("/api/queue/{entry_id}", tags=["queue"])
async def remove_from_queue(entry_id: int, reason: Optional[str] = None, admin: dict = Depends(get_current_admin)) -> dict:
    success, message = queue_manager.remove_from_queue(entry_id, reason)
    if not success:
        raise HTTPException(status_code=404, detail=message)
    return {"success": True, "message": message}


@app.post("/api/queue/reorder", tags=["queue"])
async def reorder_queue(order: List[int], admin: dict = Depends(get_current_admin)) -> dict:
    success, message = queue_manager.reorder_queue(order)
    if not success:
        raise HTTPException(status_code=400, detail=message)
    return {"success": True, "message": message}


@app.get("/api/queue/search", tags=["queue"])
async def search_queue(q: str, admin: dict = Depends(get_current_admin)) -> dict:
    entries = queue_manager.search_queue(q)
    return {"entries": entries, "count": len(entries)}


@app.get("/api/queue/stats", tags=["queue"])
async def get_stats(admin: dict = Depends(get_current_admin)) -> dict:
    stats = queue_manager.get_statistics()
    stats["playback_state"] = queue_manager.get_playback_state()
    return stats


@app.get("/api/filters/blocked-domains", tags=["filters"])
async def get_blocked_domains(admin: dict = Depends(get_current_admin)) -> dict:
    domains = filter_engine.get_all_blocked_domains()
    return {"domains": domains, "count": len(domains)}


@app.post("/api/filters/blocked-domains", tags=["filters"])
async def add_blocked_domain(request: BlockedDomainRequest, admin: dict = Depends(require_super_admin)) -> dict:
    success = filter_engine.add_blocked_domain(request.domain, request.reason, admin["username"])
    if not success:
        raise HTTPException(status_code=400, detail="Failed to add domain")
    return {"success": True, "message": f"Domain blocked: {request.domain}"}


@app.delete("/api/filters/blocked-domains/{domain}", tags=["filters"])
async def remove_blocked_domain(domain: str, admin: dict = Depends(require_super_admin)) -> dict:
    success = filter_engine.remove_blocked_domain(domain)
    if not success:
        raise HTTPException(status_code=404, detail="Domain not found")
    return {"success": True, "message": f"Domain unblocked: {domain}"}


@app.get("/api/filters/blocked-keywords", tags=["filters"])
async def get_blocked_keywords(admin: dict = Depends(get_current_admin)) -> dict:
    keywords = filter_engine.get_all_blocked_keywords()
    return {"keywords": keywords, "count": len(keywords)}


@app.post("/api/filters/blocked-keywords", tags=["filters"])
async def add_blocked_keyword(request: BlockedKeywordRequest, admin: dict = Depends(require_super_admin)) -> dict:
    success = filter_engine.add_blocked_keyword(
        keyword=request.keyword,
        reason=request.reason,
        is_regex=request.is_regex,
        admin_username=admin["username"],
    )
    if not success:
        raise HTTPException(status_code=400, detail="Failed to add keyword")
    return {"success": True, "message": f"Keyword blocked: {request.keyword}"}


@app.delete("/api/filters/blocked-keywords/{keyword}", tags=["filters"])
async def delete_blocked_keyword(keyword: str, admin: dict = Depends(require_super_admin)) -> dict:
    success = filter_engine.remove_blocked_keyword(keyword)
    if not success:
        raise HTTPException(status_code=404, detail="Keyword not found")
    return {"success": True, "message": f"Keyword unblocked: {keyword}"}


@app.get("/api/settings", tags=["settings"])
async def get_app_settings(admin: dict = Depends(get_current_admin)) -> dict:
    return {"settings": _load_persistent_settings()}


@app.put("/api/settings", tags=["settings"])
async def update_app_settings(request: AppSettingsUpdateRequest, admin: dict = Depends(get_current_admin)) -> dict:
    payload = request.dict(exclude_unset=True)
    if not payload:
        raise HTTPException(status_code=400, detail="No settings provided")
    if "preferred_theme" in payload and payload["preferred_theme"] not in {"light", "dark"}:
        raise HTTPException(status_code=400, detail="Invalid preferred theme")
    if "autoplay_timeout_seconds" in payload and int(payload["autoplay_timeout_seconds"]) < 0:
        raise HTTPException(status_code=400, detail="Invalid autoplay timeout")
    settings_payload = _upsert_app_settings(payload)
    return {"success": True, "message": "Settings updated", "settings": settings_payload}


@app.delete("/api/settings/{key}", tags=["settings"])
async def reset_app_setting(key: str, admin: dict = Depends(get_current_admin)) -> dict:
    if key not in DEFAULT_APP_SETTINGS:
        raise HTTPException(status_code=404, detail="Setting not found")
    with Database.session_context() as session:
        row = session.query(AppSetting).filter(AppSetting.key == key).first()
        if row:
            session.delete(row)
            session.commit()
    return {"success": True, "message": f"Setting reset: {key}", "settings": _load_persistent_settings()}


@app.get("/api/proxy/allowlist", tags=["proxy"])
async def get_proxy_allowlist(admin: dict = Depends(get_current_admin)) -> dict:
    settings = _load_persistent_settings()
    list_val = settings.get("proxied_page_allowlist", []) or []
    return {"domains": list(list_val), "count": len(list_val)}


@app.post("/api/proxy/allowlist", tags=["proxy"])
async def add_proxy_allowlist_item(request: BlockedDomainRequest, admin: dict = Depends(require_super_admin)) -> dict:
    domain = (request.domain or "").strip().lower()
    if not domain:
        raise HTTPException(status_code=400, detail="Domain is required")
    settings = _load_persistent_settings()
    current = settings.get("proxied_page_allowlist", []) or []
    if domain in current:
        return {"success": True, "message": "Domain already present", "domains": current}
    current.append(domain)
    _upsert_app_settings({"proxied_page_allowlist": current})
    return {"success": True, "message": f"Domain added: {domain}", "domains": current}


@app.delete("/api/proxy/allowlist/{domain}", tags=["proxy"])
async def remove_proxy_allowlist_item(domain: str, admin: dict = Depends(require_super_admin)) -> dict:
    d = (domain or "").strip().lower()
    settings = _load_persistent_settings()
    current = settings.get("proxied_page_allowlist", []) or []
    if d not in current:
        raise HTTPException(status_code=404, detail="Domain not found in allowlist")
    new_list = [x for x in current if x != d]
    _upsert_app_settings({"proxied_page_allowlist": new_list})
    return {"success": True, "message": f"Domain removed: {d}", "domains": new_list}


@app.post("/api/embed/check", response_model=EmbedCheckResponse, tags=["embed"])
async def check_embed(request: EmbedCheckRequest, http_request: Request, admin: dict = Depends(get_current_admin)) -> dict:
    url = _validate_external_url(request.url)
    runtime_config = await _guard_external_fetch(http_request, url)

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=runtime_config["embed_timeout_seconds"]) as client:
            response = await client.get(url)
    except Exception:
        return {
            "url": url,
            "status_code": 0,
            "embeddable": False,
            "x_frame_options": None,
            "content_security_policy": None,
        }

    headers = {key.lower(): value for key, value in response.headers.items()}
    x_frame_options = headers.get("x-frame-options")
    csp = headers.get("content-security-policy") or headers.get("content-security-policy-report-only")
    embeddable = True
    if x_frame_options and any(token in x_frame_options.lower() for token in ("deny", "sameorigin")):
        embeddable = False
    if csp and "frame-ancestors" in csp and any(token in csp.lower() for token in ("'none'", "'self'", "none", "self")):
        embeddable = False

    return {
        "url": url,
        "status_code": response.status_code,
        "embeddable": embeddable,
        "x_frame_options": x_frame_options,
        "content_security_policy": csp,
    }


@app.get("/api/embed/detect", tags=["embed"])
async def detect_content(url: str = Query(...), admin: dict = Depends(get_current_admin)) -> dict:
    detected = _detect_content_type(_validate_external_url(url))
    record_diagnostic("embed", "content_detected", url=url, detected_type=detected["type"])
    return detected


@app.get("/api/embed/proxy", response_class=HTMLResponse, include_in_schema=False)
async def embed_proxy(request: Request, url: str) -> HTMLResponse:
    url = _validate_external_url(url)
    runtime_config = await _guard_external_fetch(request, url)
    # allow admin to enable/disable full proxied pages via settings
    if not runtime_config.get("allow_proxied_pages"):
        raise HTTPException(status_code=403, detail="Proxied pages are disabled by server settings")
    # enforce domain allowlist if configured
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    allowlist = runtime_config.get("proxied_page_allowlist", []) or []
    def _host_matches_pattern(h: str, pattern: str) -> bool:
        p = pattern.lower().strip()
        if p.startswith("*."):
            return h == p[2:] or h.endswith('.' + p[2:])
        return h == p

    if allowlist:
        matched = any(_host_matches_pattern(host, p) for p in allowlist)
        if not matched:
            raise HTTPException(status_code=403, detail="Host not allowed for proxied pages")
    try:
        body, _ = await _fetch_text_response(
            url,
            timeout_seconds=runtime_config["embed_timeout_seconds"],
            max_bytes=runtime_config["embed_max_response_bytes"],
        )
    except Exception as exc:
        record_diagnostic("embed", "proxy_failed", level="ERROR", url=url, error=str(exc))
        return HTMLResponse(
            f"<html><body style='font-family:Segoe UI,Arial,sans-serif;padding:24px;'><h2>Unable to load page</h2><p>{url}</p></body></html>",
            status_code=502,
        )

    try:
        soup = BeautifulSoup(body, "html.parser")

        # Remove CSP / frame-ancestors meta tags and base tags which affect resource resolution
        for meta in soup.find_all("meta"):
            http_equiv = (meta.get("http-equiv") or "").lower()
            name = (meta.get("name") or "").lower()
            if "content-security-policy" in http_equiv or "content-security-policy" in name or "frame-ancestors" in (meta.get("content") or ""):
                meta.decompose()
        for base in soup.find_all("base"):
            base.decompose()

        # Rewrite resource URLs to route through our resource proxy
        resource_tags = {"img", "script", "source", "video", "audio", "link"}
        resource_attrs = ["src", "href", "poster", "data-src"]
        for tag in soup.find_all(True):
            # Make anchors open in a new tab instead of navigating inside the proxied view
            if tag.name == "a" and tag.has_attr("href"):
                try:
                    abs_link = urljoin(url, tag["href"])
                    tag["href"] = abs_link
                    tag["target"] = "_blank"
                    tag["rel"] = "noreferrer noopener"
                except Exception:
                    pass

            if tag.name in resource_tags:
                for attr in resource_attrs:
                    if tag.has_attr(attr):
                        try:
                            raw = tag[attr]
                            if not raw:
                                continue
                            abs_res = urljoin(url, raw)
                            proxied = f"/api/embed/resource?url={quote(abs_res, safe='')}"
                            tag[attr] = proxied
                        except Exception:
                            # leave the attribute unchanged on error
                            continue

        # Remove potentially dangerous interactive elements and scripts before sanitizing
        for bad in soup(["iframe", "form", "input", "button", "noscript"]):
            bad.decompose()

        sanitized = _sanitize_html(str(soup))
        return HTMLResponse(sanitized)
    except Exception as exc:
        record_diagnostic("embed", "proxy_postprocess_failed", level="ERROR", url=url, error=str(exc))
        return HTMLResponse(_sanitize_html(body))


@app.get("/api/embed/readable", response_class=HTMLResponse, include_in_schema=False)
async def embed_readable(request: Request, url: str) -> HTMLResponse:
    url = _validate_external_url(url)
    runtime_config = await _guard_external_fetch(request, url)
    # Return cached readable HTML when available
    cached = _readable_cache_get(url)
    if cached:
        return HTMLResponse(cached)
    try:
        body, _ = await _fetch_text_response(
            url,
            timeout_seconds=runtime_config["embed_timeout_seconds"],
            max_bytes=runtime_config["embed_max_response_bytes"],
        )
    except Exception as exc:
        record_diagnostic("embed", "readable_failed", level="ERROR", url=url, error=str(exc))
        return HTMLResponse(
            f"<html><body style='font-family:Segoe UI,Arial,sans-serif;padding:24px;'><h2>Unable to load readable view</h2><p>{url}</p></body></html>",
            status_code=502,
        )
    html = _extract_readable_content(body, url)
    try:
        _readable_cache_set(url, html)
    except Exception:
        pass
    return HTMLResponse(html)


@app.get("/api/embed/resource", include_in_schema=False)
async def embed_resource(request: Request, url: str) -> Response:
    """Proxy a single resource (images, CSS, media) while enforcing SSRF protections and rate-limits.

    This endpoint is intentionally minimal: it forwards the resource bytes and the upstream
    `Content-Type` header where possible. It is not a full-featured CDN and should be
    used sparingly (rate-limited above).
    """
    url = _validate_external_url(url)
    runtime_config = await _guard_external_fetch(request, url)

    if not runtime_config.get("allow_proxied_pages"):
        raise HTTPException(status_code=403, detail="Resource proxying is disabled by server settings")

    # enforce domain allowlist for resources if configured
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    allowlist = runtime_config.get("proxied_page_allowlist", []) or []
    def _host_matches_pattern(h: str, pattern: str) -> bool:
        p = pattern.lower().strip()
        if p.startswith("*."):
            return h == p[2:] or h.endswith('.' + p[2:])
        return h == p

    if allowlist:
        matched = any(_host_matches_pattern(host, p) for p in allowlist)
        if not matched:
            raise HTTPException(status_code=403, detail="Host not allowed for proxied resources")

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=runtime_config["embed_timeout_seconds"]) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            content = resp.content
            content_type = resp.headers.get("content-type") or "application/octet-stream"
            headers = {"cache-control": "max-age=300, public"}
            return Response(content=content, media_type=content_type, headers=headers)
    except httpx.HTTPStatusError as exc:
        record_diagnostic("embed", "resource_fetch_failed", level="ERROR", url=url, status=exc.response.status_code)
        raise HTTPException(status_code=502, detail="Upstream resource error")
    except Exception as exc:
        record_diagnostic("embed", "resource_fetch_failed", level="ERROR", url=url, error=str(exc))
        raise HTTPException(status_code=502, detail="Unable to fetch resource")


@app.get("/api/diagnostics", tags=["diagnostics"])
async def get_diagnostics(admin: dict = Depends(get_current_admin)) -> dict:
    return {
        "events": diagnostics_buffer.snapshot(),
        "runtime": runtime_state.snapshot(),
        "playback_state": queue_manager.get_playback_state(),
    }


@app.get("/", include_in_schema=False)
async def root() -> FileResponse:
    return FileResponse(INDEX_PATH)


@app.get("/dashboard", include_in_schema=False)
async def dashboard() -> FileResponse:
    return FileResponse(INDEX_PATH)


@app.get("/queue", include_in_schema=False)
async def queue_page() -> RedirectResponse:
    return RedirectResponse(url='/#/queue')


@app.get("/filters", include_in_schema=False)
async def filters_page() -> RedirectResponse:
    return RedirectResponse(url='/#/filters')


@app.get("/settings", include_in_schema=False)
async def settings_page() -> RedirectResponse:
    return RedirectResponse(url='/#/settings')


def create_app() -> FastAPI:
    if not Database.is_initialized():
        Database.initialize()
        SecurityManager.init_default_admin()
    return app
