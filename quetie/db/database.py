"""
Database initialization and management for Quetie_mbg
Handles SQLAlchemy session management and schema creation
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from contextlib import contextmanager
from quetie.config.settings import settings
from quetie.db.models import Base
from quetie.utils.logger import setup_logger

logger = setup_logger(__name__)


class Database:
    """Database connection and session management"""
    
    _engine = None
    _session_maker = None
    
    @classmethod
    def initialize(cls, url: str = None) -> None:
        """
        Initialize database connection
        
        Args:
            url: Database URL (uses settings.DATABASE_URL if not provided)
        """
        db_url = url or settings.DATABASE_URL
        logger.info(f"Initializing database: {db_url}")
        
        # Configure connection pooling based on database type
        if "sqlite" in db_url:
            # SQLite uses StaticPool for compatibility
            cls._engine = create_engine(
                db_url,
                connect_args={"check_same_thread": False},
                poolclass=StaticPool,
                echo=settings.DEBUG
            )
        else:
            # PostgreSQL and other databases
            cls._engine = create_engine(
                db_url,
                pool_size=10,
                max_overflow=20,
                pool_pre_ping=True,
                echo=settings.DEBUG
            )
        
        # Create session factory
        cls._session_maker = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=cls._engine
        )
        
        # Create all tables
        Base.metadata.create_all(bind=cls._engine)
        logger.info("Database tables created/verified")
    
    @classmethod
    def get_session(cls) -> Session:
        """
        Get a new database session
        
        Returns:
            SQLAlchemy Session
        """
        if cls._session_maker is None:
            cls.initialize()
        return cls._session_maker()
    
    @classmethod
    @contextmanager
    def session_context(cls):
        """
        Context manager for database sessions
        Automatically handles commit/rollback
        
        Usage:
            with Database.session_context() as session:
                # Use session
                pass
        """
        session = cls.get_session()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            session.close()
    
    @classmethod
    def close(cls) -> None:
        """Close database connections"""
        if cls._engine:
            cls._engine.dispose()
            logger.info("Database connections closed")
    
    @classmethod
    def health_check(cls) -> bool:
        """
        Perform database health check
        
        Returns:
            True if database is accessible, False otherwise
        """
        try:
            with cls.session_context() as session:
                session.execute("SELECT 1")
            logger.debug("Database health check passed")
            return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False


# Dependency for FastAPI
def get_db():
    """FastAPI dependency for database sessions"""
    db = Database.get_session()
    try:
        yield db
    finally:
        db.close()
