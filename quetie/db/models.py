"""
Database models for Quetie_mbg using SQLAlchemy
Supports SQLite (dev) and PostgreSQL (production)
"""

from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, Boolean, Text, ForeignKey, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import enum

Base = declarative_base()


class Admin(Base):
    """Admin user model for dashboard authentication"""
    __tablename__ = "admins"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    email = Column(String(100), unique=True, index=True)
    is_active = Column(Boolean, default=True)
    is_super_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    sessions = relationship("AdminSession", back_populates="admin", cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        return f"<Admin {self.username}>"


class AdminSession(Base):
    """Admin session tracking for JWT tokens"""
    __tablename__ = "admin_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    admin_id = Column(Integer, ForeignKey("admins.id"), nullable=False)
    token = Column(String(500), unique=True, index=True)
    ip_address = Column(String(50))
    user_agent = Column(String(255))
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    admin = relationship("Admin", back_populates="sessions")
    
    def is_valid(self) -> bool:
        """Check if session is still valid"""
        return datetime.utcnow() < self.expires_at
    
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
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    played_at = Column(DateTime)
    removed_at = Column(DateTime)
    
    def __repr__(self) -> str:
        return f"<QueueEntry {self.id} - {self.status}>"
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "url": self.url,
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
    created_at = Column(DateTime, default=datetime.utcnow)
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
    created_at = Column(DateTime, default=datetime.utcnow)
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
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
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
