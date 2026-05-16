"""
FastAPI web application for Quetie_mbg
Dashboard API and health endpoints
"""

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
from pathlib import Path

from quetie.config.settings import settings
from quetie.db.database import Database
from quetie.db.models import Admin
from quetie.queue.manager import queue_manager
from quetie.filtering.filters import filter_engine
from quetie.web.auth import SecurityManager
from quetie.utils.logger import setup_logger

logger = setup_logger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Quetie_mbg API",
    description="Twitch Queue Management Bot API",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models for request/response
class LoginRequest(BaseModel):
    """Login request model"""
    username: str
    password: str


class LoginResponse(BaseModel):
    """Login response model"""
    success: bool
    token: Optional[str] = None
    message: str = ""


class QueueEntryRequest(BaseModel):
    """Queue entry request"""
    url: str
    submitter_username: str
    notes: Optional[str] = None


class QueueEntryResponse(BaseModel):
    """Queue entry response"""
    id: int
    url: str
    status: str
    submitter_username: str
    position: int
    created_at: str


class BlockedDomainRequest(BaseModel):
    """Blocked domain request"""
    domain: str
    reason: Optional[str] = None


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    database: bool
    bot: bool
    version: str


# Dependency for authentication
def get_current_admin(authorization: str = None) -> dict:
    """
    Get current authenticated admin from JWT token
    
    Args:
        authorization: Authorization header (Bearer token)
    
    Returns:
        Admin info dict
    
    Raises:
        HTTPException if not authenticated
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization header"
        )
    
    token = authorization[7:]  # Remove "Bearer " prefix
    admin = SecurityManager.get_admin_from_token(token)
    
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )
    
    return admin


# ========== Health & Status Endpoints ==========

@app.get("/health", tags=["health"])
async def health_check() -> HealthResponse:
    """
    Health check endpoint for uptime monitoring
    
    Returns:
        Health status of all components
    """
    db_health = Database.health_check()
    
    return HealthResponse(
        status="healthy" if db_health else "degraded",
        database=db_health,
        bot=True,  # Bot status checked separately
        version="1.0.0"
    )


# ========== Authentication Endpoints ==========

@app.post("/api/auth/login", response_model=LoginResponse, tags=["auth"])
async def login(request: LoginRequest) -> LoginResponse:
    """
    Login with admin credentials
    
    Args:
        request: Login credentials
    
    Returns:
        JWT token if successful
    """
    success, token, admin_id = SecurityManager.authenticate_admin(
        request.username,
        request.password
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    return LoginResponse(
        success=True,
        token=token,
        message="Login successful"
    )


@app.get("/api/auth/me", tags=["auth"])
async def get_current_user(admin: dict = Depends(get_current_admin)) -> dict:
    """
    Get current authenticated user info
    
    Returns:
        Current admin information
    """
    return admin


# ========== Queue Endpoints ==========

@app.get("/api/queue", tags=["queue"])
async def get_queue(
    skip: int = 0,
    limit: int = 50,
    admin: dict = Depends(get_current_admin)
) -> dict:
    """
    Get current queue
    
    Args:
        skip: Number of entries to skip
        limit: Maximum entries to return
    
    Returns:
        Queue entries and total count
    """
    entries, total = queue_manager.get_queue(limit=limit, offset=skip)
    
    return {
        "entries": entries,
        "total": total,
        "skip": skip,
        "limit": limit
    }


@app.post("/api/queue/add", tags=["queue"])
async def add_to_queue(
    request: QueueEntryRequest,
    admin: dict = Depends(get_current_admin)
) -> dict:
    """
    Add entry to queue (admin endpoint)
    
    Args:
        request: Queue entry details
    
    Returns:
        Add result with entry ID
    """
    success, message, entry_id = queue_manager.add_to_queue(
        url=request.url,
        submitter_username=request.submitter_username,
        notes=request.notes
    )
    
    if not success:
        raise HTTPException(status_code=400, detail=message)
    
    return {
        "success": True,
        "message": message,
        "entry_id": entry_id
    }


@app.post("/api/queue/{entry_id}/play", tags=["queue"])
async def mark_playing(
    entry_id: int,
    admin: dict = Depends(get_current_admin)
) -> dict:
    """
    Mark queue entry as playing
    
    Args:
        entry_id: Queue entry ID
    
    Returns:
        Operation result
    """
    success, message = queue_manager.mark_as_playing(entry_id)
    
    if not success:
        raise HTTPException(status_code=404, detail=message)
    
    return {"success": True, "message": message}


@app.post("/api/queue/{entry_id}/complete", tags=["queue"])
async def mark_completed(
    entry_id: int,
    admin: dict = Depends(get_current_admin)
) -> dict:
    """
    Mark queue entry as completed
    
    Args:
        entry_id: Queue entry ID
    
    Returns:
        Operation result
    """
    success, message = queue_manager.mark_as_completed(entry_id)
    
    if not success:
        raise HTTPException(status_code=404, detail=message)
    
    return {"success": True, "message": message}


@app.delete("/api/queue/{entry_id}", tags=["queue"])
async def remove_from_queue(
    entry_id: int,
    reason: Optional[str] = None,
    admin: dict = Depends(get_current_admin)
) -> dict:
    """
    Remove entry from queue
    
    Args:
        entry_id: Queue entry ID
        reason: Reason for removal
    
    Returns:
        Operation result
    """
    success, message = queue_manager.remove_from_queue(entry_id, reason)
    
    if not success:
        raise HTTPException(status_code=404, detail=message)
    
    return {"success": True, "message": message}


@app.post("/api/queue/reorder", tags=["queue"])
async def reorder_queue(
    order: List[int],
    admin: dict = Depends(get_current_admin)
) -> dict:
    """
    Reorder queue entries
    
    Args:
        order: List of entry IDs in desired order
    
    Returns:
        Operation result
    """
    success, message = queue_manager.reorder_queue(order)
    
    if not success:
        raise HTTPException(status_code=400, detail=message)
    
    return {"success": True, "message": message}


@app.get("/api/queue/search", tags=["queue"])
async def search_queue(
    q: str,
    admin: dict = Depends(get_current_admin)
) -> dict:
    """
    Search queue entries
    
    Args:
        q: Search query
    
    Returns:
        Matching entries
    """
    entries = queue_manager.search_queue(q)
    return {"entries": entries, "count": len(entries)}


@app.get("/api/queue/stats", tags=["queue"])
async def get_stats(admin: dict = Depends(get_current_admin)) -> dict:
    """
    Get queue statistics
    
    Returns:
        Queue statistics
    """
    return queue_manager.get_statistics()


# ========== Filtering Endpoints ==========

@app.get("/api/filters/blocked-domains", tags=["filters"])
async def get_blocked_domains(admin: dict = Depends(get_current_admin)) -> dict:
    """
    Get all blocked domains
    
    Returns:
        List of blocked domains
    """
    domains = filter_engine.get_all_blocked_domains()
    return {"domains": domains, "count": len(domains)}


@app.post("/api/filters/blocked-domains", tags=["filters"])
async def add_blocked_domain(
    request: BlockedDomainRequest,
    admin: dict = Depends(get_current_admin)
) -> dict:
    """
    Add domain to blocked list
    
    Args:
        request: Domain to block
    
    Returns:
        Operation result
    """
    success = filter_engine.add_blocked_domain(
        domain=request.domain,
        reason=request.reason,
        admin_username=admin["username"]
    )
    
    if not success:
        raise HTTPException(status_code=400, detail="Failed to add domain")
    
    return {"success": True, "message": f"Domain blocked: {request.domain}"}


@app.delete("/api/filters/blocked-domains/{domain}", tags=["filters"])
async def remove_blocked_domain(
    domain: str,
    admin: dict = Depends(get_current_admin)
) -> dict:
    """
    Remove domain from blocked list
    
    Args:
        domain: Domain to unblock
    
    Returns:
        Operation result
    """
    success = filter_engine.remove_blocked_domain(domain)
    
    if not success:
        raise HTTPException(status_code=404, detail="Domain not found")
    
    return {"success": True, "message": f"Domain unblocked: {domain}"}


@app.get("/api/filters/blocked-keywords", tags=["filters"])
async def get_blocked_keywords(admin: dict = Depends(get_current_admin)) -> dict:
    """
    Get all blocked keywords
    
    Returns:
        List of blocked keywords
    """
    keywords = filter_engine.get_all_blocked_keywords()
    return {"keywords": keywords, "count": len(keywords)}


# ========== Static Files ==========

@app.get("/", include_in_schema=False)
async def root():
    """Serve dashboard index"""
    return FileResponse("quetie/web/static/index.html")


@app.get("/dashboard", include_in_schema=False)
async def dashboard():
    """Serve dashboard"""
    return FileResponse("quetie/web/static/index.html")


def create_app() -> FastAPI:
    """Factory function to create FastAPI app"""
    # Initialize database
    Database.initialize()
    
    # Initialize default admin
    SecurityManager.init_default_admin()
    
    # Refresh filter cache
    filter_engine.refresh_filters()
    
    logger.info("FastAPI app created and initialized")
    return app
