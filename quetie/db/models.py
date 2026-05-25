"""
Database models for Quetie_mbg using SQLAlchemy
Supports SQLite (dev) and PostgreSQL (production)
"""

import json
from urllib.parse import urlparse
from sqlalchemy import Column, String, Integer, DateTime, Boolean, Text, ForeignKey, Enum
from sqlalchemy.orm import declarative_base, relationship
import enum
from sqlalchemy import Table

from quetie.utils.time import utc_now

Base = declarative_base()


def _derive_display_title_from_url(url: str) -> str:
    """Generate a compact display title from a URL."""
    try:
        parsed = urlparse(url)
        path_parts = [part for part in parsed.path.split('/') if part]
        if path_parts:
            candidate = path_parts[-1].replace('-', ' ').replace('_', ' ').strip()
            if candidate:
                return candidate[:80]

        domain = parsed.netloc.lower()
        if ':' in domain:
            domain = domain.split(':')[0]
        if domain:
            return domain
    except Exception:
        pass

    return url[:80]


class Admin(Base):
    """Admin user model for dashboard authentication"""
    __tablename__ = "admins"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    email = Column(String(100), unique=True, index=True)
    is_active = Column(Boolean, default=True)
    is_super_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)
    
    # Relationships
    sessions = relationship("AdminSession", back_populates="admin", cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        return f"<Admin {self.username}>"

    def to_dict(self) -> dict:
        """Convert to dictionary for dashboard/API use"""
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "is_active": self.is_active,
            "is_super_admin": self.is_super_admin,
            "role": "super_admin" if self.is_super_admin else "moderator",
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class AdminSession(Base):
    """Admin session tracking for JWT tokens"""
    __tablename__ = "admin_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    admin_id = Column(Integer, ForeignKey("admins.id"), nullable=False)
    token = Column(String(500), unique=True, index=True)
    ip_address = Column(String(50))
    user_agent = Column(String(255))
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=utc_now)
    
    # Relationships
    admin = relationship("Admin", back_populates="sessions")
    
    def is_valid(self) -> bool:
        """Check if session is still valid"""
        return utc_now() < self.expires_at
    
    def __repr__(self) -> str:
        return f"<AdminSession admin_id={self.admin_id}>"


class QueueEntryStatus(str, enum.Enum):
    """Status enum for queue entries"""
    PENDING = "pending"
    PLAYING = "playing"
    COMPLETED = "completed"
    REMOVED = "removed"
    BLOCKED = "blocked"


class QueueEntry(Base):
    """Queue entry model for storing submitted links"""
    __tablename__ = "queue_entries"
    
    id = Column(Integer, primary_key=True, index=True)
    url = Column(String(2048), nullable=False)
    status = Column(Enum(QueueEntryStatus), default=QueueEntryStatus.PENDING, index=True)
    submitter_username = Column(String(100), nullable=False)
    position = Column(Integer, default=0)
    notes = Column(Text)
    is_duplicate = Column(Boolean, default=False)
    created_at = Column(DateTime, default=utc_now, index=True)
    played_at = Column(DateTime)
    removed_at = Column(DateTime)
    
    def __repr__(self) -> str:
        return f"<QueueEntry {self.id} - {self.status}>"
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "url": self.url,
            "clip_title": _derive_display_title_from_url(self.url),
            "status": self.status.value,
            "submitter_username": self.submitter_username,
            "position": self.position,
            "notes": self.notes,
            "is_duplicate": self.is_duplicate,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "played_at": self.played_at.isoformat() if self.played_at else None,
        }


class BlockedDomain(Base):
    """Model for storing blocked/filtered domains"""
    __tablename__ = "blocked_domains"
    
    id = Column(Integer, primary_key=True, index=True)
    domain = Column(String(255), unique=True, index=True, nullable=False)
    reason = Column(String(255))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utc_now)
    created_by = Column(String(100))  # Admin username
    
    def __repr__(self) -> str:
        return f"<BlockedDomain {self.domain}>"
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "domain": self.domain,
            "reason": self.reason,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class BlockedKeyword(Base):
    """Model for storing blocked keywords/patterns"""
    __tablename__ = "blocked_keywords"
    
    id = Column(Integer, primary_key=True, index=True)
    keyword = Column(String(255), unique=True, index=True, nullable=False)
    reason = Column(String(255))
    is_active = Column(Boolean, default=True)
    is_regex = Column(Boolean, default=False)
    created_at = Column(DateTime, default=utc_now)
    created_by = Column(String(100))
    
    def __repr__(self) -> str:
        return f"<BlockedKeyword {self.keyword}>"
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "keyword": self.keyword,
            "reason": self.reason,
            "is_active": self.is_active,
            "is_regex": self.is_regex,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class BotStatistic(Base):
    """Model for tracking bot statistics"""
    __tablename__ = "bot_statistics"
    
    id = Column(Integer, primary_key=True, index=True)
    total_links_submitted = Column(Integer, default=0)
    total_links_accepted = Column(Integer, default=0)
    total_links_rejected = Column(Integer, default=0)
    total_links_played = Column(Integer, default=0)
    last_updated = Column(DateTime, default=utc_now, onupdate=utc_now)
    
    def __repr__(self) -> str:
        return f"<BotStatistic>"
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            "total_links_submitted": self.total_links_submitted,
            "total_links_accepted": self.total_links_accepted,
            "total_links_rejected": self.total_links_rejected,
            "total_links_played": self.total_links_played,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
        }


class AppSetting(Base):
    """Persistent app setting stored as JSON value per key"""
    __tablename__ = "app_settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, index=True, nullable=False)
    value = Column(Text, nullable=False)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    def __repr__(self) -> str:
        return f"<AppSetting {self.key}>"

    def to_dict(self) -> dict:
        try:
            parsed_value = json.loads(self.value)
        except Exception:
            parsed_value = self.value

        return {
            "key": self.key,
            "value": parsed_value,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class PasswordResetToken(Base):
    """Secure password reset tokens for team members"""
    __tablename__ = "password_reset_tokens"

    id = Column(Integer, primary_key=True, index=True)
    admin_id = Column(Integer, ForeignKey("admins.id"), nullable=False)
    token = Column(String(255), unique=True, index=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False)
    created_at = Column(DateTime, default=utc_now)

    # Relationships
    admin = relationship("Admin")

    def is_valid(self) -> bool:
        """Check if token is still valid and unused"""
        return utc_now() < self.expires_at and not self.used

    def __repr__(self) -> str:
        return f"<PasswordResetToken admin_id={self.admin_id}>"


# RBAC: Roles and Permissions
admin_roles = Table(
    'admin_roles',
    Base.metadata,
    Column('admin_id', Integer, ForeignKey('admins.id'), primary_key=True),
    Column('role_id', Integer, ForeignKey('roles.id'), primary_key=True),
)


class Role(Base):
    __tablename__ = 'roles'

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(80), unique=True, nullable=False)
    description = Column(String(255))
    created_at = Column(DateTime, default=utc_now)

    permissions = relationship('Permission', back_populates='role', cascade='all, delete-orphan')
    admins = relationship('Admin', secondary=admin_roles, backref='roles')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'permissions': [p.to_dict() for p in (self.permissions or [])],
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class Permission(Base):
    __tablename__ = 'permissions'

    id = Column(Integer, primary_key=True, index=True)
    role_id = Column(Integer, ForeignKey('roles.id'), nullable=False)
    key = Column(String(120), nullable=False)
    description = Column(String(255))

    role = relationship('Role', back_populates='permissions')

    def to_dict(self):
        return {'id': self.id, 'key': self.key, 'description': self.description}


class AuditLog(Base):
    __tablename__ = 'audit_logs'

    id = Column(Integer, primary_key=True, index=True)
    actor = Column(String(100))
    action = Column(String(255))
    target = Column(String(255))
    details = Column(Text)
    created_at = Column(DateTime, default=utc_now)

    def to_dict(self):
        return {
            'id': self.id,
            'actor': self.actor,
            'action': self.action,
            'target': self.target,
            'details': self.details,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
