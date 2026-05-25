"""
Authentication and security for Quetie_mbg web dashboard
JWT-based authentication with admin credentials
"""

import jwt
import bcrypt
import uuid
from datetime import timedelta
from typing import Optional, Tuple
from quetie.config.settings import settings
from quetie.db.database import Database
from quetie.db.models import Admin, AdminSession
from quetie.db.models import Role, Permission, AuditLog
from quetie.utils.logger import setup_logger
from quetie.utils.time import utc_now
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status, Depends
from fastapi import Header

from quetie.db.models import AuditLog


def require_permission(permission_key: str):
    """Return a FastAPI dependency that enforces a permission key for the current admin."""
    def _dependency(admin_info: dict = Depends(lambda authorization=Header(None): SecurityManager.get_admin_from_token(authorization[7:]) if authorization and authorization.startswith('Bearer ') else None)):
        if not admin_info:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Unauthorized')
        # Super admin bypass
        if admin_info.get('is_super_admin'):
            return admin_info
        perms = admin_info.get('permissions') or []
        if permission_key not in perms:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Permission denied')
        return admin_info
    return _dependency


def audit_event(actor: str, action: str, target: str = None, details: str = None):
    try:
        with Database.session_context() as session:
            log = AuditLog(actor=actor, action=action, target=target or '', details=details or '')
            session.add(log)
            session.commit()
    except Exception:
        logger.exception('Failed to write audit log')

logger = setup_logger(__name__)


class SecurityManager:
    """Manages authentication, JWT tokens, and security"""
    
    @staticmethod
    def hash_password(password: str) -> str:
        """
        Hash password using bcrypt
        
        Args:
            password: Plain text password
        
        Returns:
            Hashed password
        """
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    
    @staticmethod
    def verify_password(password: str, password_hash: str) -> bool:
        """
        Verify password against hash
        
        Args:
            password: Plain text password
            password_hash: Hashed password
        
        Returns:
            True if password matches, False otherwise
        """
        try:
            return bcrypt.checkpw(password.encode(), password_hash.encode())
        except Exception as e:
            logger.error(f"Error verifying password: {e}")
            return False
    
    @staticmethod
    def generate_jwt(admin_id: int, expires_in_hours: int = None) -> str:
        """
        Generate JWT token
        
        Args:
            admin_id: Admin user ID
            expires_in_hours: Token expiration time in hours
        
        Returns:
            JWT token string
        """
        expires_in = expires_in_hours or settings.JWT_EXPIRATION_HOURS
        issued_at = utc_now()
        expiration = issued_at + timedelta(hours=expires_in)
        
        payload = {
            "admin_id": admin_id,
            "exp": expiration,
            "iat": issued_at,
            "jti": uuid.uuid4().hex
        }
        
        token = jwt.encode(
            payload,
            settings.JWT_SECRET,
            algorithm=settings.JWT_ALGORITHM
        )
        
        logger.debug(f"Generated JWT for admin_id: {admin_id}")
        return token
    
    @staticmethod
    def verify_jwt(token: str) -> Tuple[bool, Optional[int]]:
        """
        Verify and decode JWT token
        
        Args:
            token: JWT token string
        
        Returns:
            Tuple of (is_valid: bool, admin_id: Optional[int])
        """
        try:
            payload = jwt.decode(
                token,
                settings.JWT_SECRET,
                algorithms=[settings.JWT_ALGORITHM]
            )
            admin_id = payload.get("admin_id")
            
            logger.debug(f"Verified JWT for admin_id: {admin_id}")
            return True, admin_id
        except jwt.ExpiredSignatureError:
            logger.warning("JWT token expired")
            return False, None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid JWT token: {e}")
            return False, None
        except Exception as e:
            logger.error(f"Error verifying JWT: {e}")
            return False, None
    
    @staticmethod
    def authenticate_admin(username: str, password: str) -> Tuple[bool, Optional[str], Optional[int]]:
        """
        Authenticate admin user and return JWT token
        
        Args:
            username: Admin username
            password: Admin password
        
        Returns:
            Tuple of (success: bool, token: Optional[str], admin_id: Optional[int])
        """
        try:
            with Database.session_context() as session:
                admin = session.query(Admin).filter(
                    Admin.username == username,
                    Admin.is_active == True
                ).first()
                
                if not admin:
                    logger.warning(f"Login attempt with non-existent username: {username}")
                    return False, None, None
                
                if not SecurityManager.verify_password(password, admin.password_hash):
                    logger.warning(f"Failed login attempt for admin: {username}")
                    return False, None, None
                
                # Generate token
                token = SecurityManager.generate_jwt(admin.id)
                
                # Store session in database; retry on token uniqueness collision
                attempts = 0
                while attempts < 3:
                    try:
                        session_record = AdminSession(
                            admin_id=admin.id,
                            token=token,
                            expires_at=utc_now() + timedelta(hours=settings.JWT_EXPIRATION_HOURS)
                        )
                        session.add(session_record)
                        session.commit()
                        break
                    except IntegrityError:
                        session.rollback()
                        attempts += 1
                        logger.warning("Token collision detected, regenerating token")
                        token = SecurityManager.generate_jwt(admin.id)

                if attempts >= 3:
                    logger.error("Failed to persist admin session after multiple attempts")
                    return False, None, None
                
                logger.info(f"Successful login for admin: {username}")
                return True, token, admin.id
        
        except Exception as e:
            logger.error(f"Error during authentication: {e}")
            return False, None, None
    
    @staticmethod
    def get_admin_from_token(token: str) -> Optional[dict]:
        """
        Get admin info from JWT token
        
        Args:
            token: JWT token string
        
        Returns:
            Admin info dict or None if invalid
        """
        is_valid, admin_id = SecurityManager.verify_jwt(token)
        
        if not is_valid or admin_id is None:
            return None

        try:
            admin_id = int(admin_id)
        except (TypeError, ValueError):
            logger.warning(f"Invalid admin_id in JWT payload: {admin_id!r}")
            return None
        
        try:
            with Database.session_context() as session:
                admin = session.get(Admin, admin_id)
                
                if admin and admin.is_active:
                    # include role names for convenience
                    role_names = [r.name for r in (admin.roles or [])]
                    # include permissions aggregated from roles
                    perm_keys = []
                    for r in (admin.roles or []):
                        for p in (r.permissions or []):
                            if p.key not in perm_keys:
                                perm_keys.append(p.key)

                    return {
                        "id": admin.id,
                        "username": admin.username,
                        "email": admin.email,
                        "is_super_admin": admin.is_super_admin,
                        "roles": role_names,
                        "permissions": perm_keys,
                    }
        except Exception as e:
            logger.error(f"Error getting admin from token: {e}")
        
        return None
    
    @staticmethod
    def init_default_admin() -> bool:
        """
        Initialize default admin user if none exists
        Uses credentials from environment variables
        
        Returns:
            True if admin exists or was created, False if error
        """
        try:
            with Database.session_context() as session:
                # Check if any admin exists
                existing_admin = session.query(Admin).first()
                if existing_admin:
                    logger.info("Admin user already exists")
                    return True
                
                # Create default admin from environment
                username = settings.ADMIN_USERNAME
                password_hash = settings.ADMIN_PASSWORD_HASH

                # In production we require an explicit ADMIN_PASSWORD_HASH to be set
                if settings.is_production() and not password_hash:
                    logger.error("ADMIN_PASSWORD_HASH must be set in production to create default admin")
                    return False

                if not password_hash:
                    # Development fallback: create a random password and log a warning
                    default_password = "admin123"
                    password_hash = SecurityManager.hash_password(default_password)
                    logger.warning("Using default password in development - change before deploying to production")

                admin = Admin(
                    username=username,
                    password_hash=password_hash,
                    is_active=True,
                    is_super_admin=True
                )
                session.add(admin)
                session.commit()

                # create a default 'super_admin' role and grant all placeholder perms
                try:
                    role = Role(name='super_admin', description='Full access')
                    session.add(role)
                    session.commit()
                    # attach admin to role
                    admin.roles.append(role)
                    session.commit()
                except Exception:
                    session.rollback()
                
                logger.info(f"Default admin created: {username}")
                return True
        
        except Exception as e:
            logger.error(f"Error initializing default admin: {e}")
            return False
