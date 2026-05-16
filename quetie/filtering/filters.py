"""
Link filtering engine for Quetie_mbg
Manages and applies filtering rules against queue submissions
"""

import re
from typing import List, Dict, Tuple, Optional
from quetie.db.database import Database
from quetie.db.models import BlockedDomain, BlockedKeyword
from quetie.utils.logger import setup_logger

logger = setup_logger(__name__)


class FilterEngine:
    """Central filtering engine for link validation and blocking"""
    
    def __init__(self):
        """Initialize filter engine with default rules"""
        self._blocked_domains_cache = []
        self._blocked_keywords_cache = []
        self._cache_valid = False
    
    def refresh_filters(self) -> None:
        """Refresh filter cache from database"""
        try:
            with Database.session_context() as session:
                # Load active blocked domains
                domains = session.query(BlockedDomain).filter(
                    BlockedDomain.is_active == True
                ).all()
                self._blocked_domains_cache = [d.domain for d in domains]
                
                # Load active blocked keywords
                keywords = session.query(BlockedKeyword).filter(
                    BlockedKeyword.is_active == True
                ).all()
                self._blocked_keywords_cache = [k.keyword for k in keywords]
                
                self._cache_valid = True
                logger.debug(f"Filter cache refreshed: {len(self._blocked_domains_cache)} domains, {len(self._blocked_keywords_cache)} keywords")
        except Exception as e:
            logger.error(f"Error refreshing filters: {e}")
            self._cache_valid = False
    
    def get_blocked_domains(self) -> List[str]:
        """Get list of blocked domains"""
        if not self._cache_valid:
            self.refresh_filters()
        return self._blocked_domains_cache
    
    def get_blocked_keywords(self) -> List[str]:
        """Get list of blocked keywords"""
        if not self._cache_valid:
            self.refresh_filters()
        return self._blocked_keywords_cache
    
    def add_blocked_domain(
        self,
        domain: str,
        reason: str = None,
        admin_username: str = "system"
    ) -> bool:
        """
        Add a domain to the blocked list
        
        Args:
            domain: Domain to block
            reason: Reason for blocking
            admin_username: Username of admin adding block
        
        Returns:
            True if successfully added, False otherwise
        """
        try:
            with Database.session_context() as session:
                # Check if already exists
                existing = session.query(BlockedDomain).filter(
                    BlockedDomain.domain == domain.lower()
                ).first()
                
                if existing:
                    logger.warning(f"Domain already blocked: {domain}")
                    return False
                
                blocked_domain = BlockedDomain(
                    domain=domain.lower(),
                    reason=reason,
                    created_by=admin_username
                )
                session.add(blocked_domain)
                session.commit()
                logger.info(f"Domain blocked: {domain}")
                self._cache_valid = False
                return True
        except Exception as e:
            logger.error(f"Error adding blocked domain: {e}")
            return False
    
    def remove_blocked_domain(self, domain: str) -> bool:
        """
        Remove a domain from the blocked list
        
        Args:
            domain: Domain to unblock
        
        Returns:
            True if successfully removed, False otherwise
        """
        try:
            with Database.session_context() as session:
                blocked_domain = session.query(BlockedDomain).filter(
                    BlockedDomain.domain == domain.lower()
                ).first()
                
                if not blocked_domain:
                    logger.warning(f"Domain not found in blocked list: {domain}")
                    return False
                
                session.delete(blocked_domain)
                session.commit()
                logger.info(f"Domain unblocked: {domain}")
                self._cache_valid = False
                return True
        except Exception as e:
            logger.error(f"Error removing blocked domain: {e}")
            return False
    
    def add_blocked_keyword(
        self,
        keyword: str,
        reason: str = None,
        is_regex: bool = False,
        admin_username: str = "system"
    ) -> bool:
        """
        Add a keyword to the blocked list
        
        Args:
            keyword: Keyword to block
            reason: Reason for blocking
            is_regex: Whether keyword is a regex pattern
            admin_username: Username of admin adding block
        
        Returns:
            True if successfully added, False otherwise
        """
        try:
            with Database.session_context() as session:
                # Check if already exists
                existing = session.query(BlockedKeyword).filter(
                    BlockedKeyword.keyword == keyword
                ).first()
                
                if existing:
                    logger.warning(f"Keyword already blocked: {keyword}")
                    return False
                
                blocked_keyword = BlockedKeyword(
                    keyword=keyword,
                    reason=reason,
                    is_regex=is_regex,
                    created_by=admin_username
                )
                session.add(blocked_keyword)
                session.commit()
                logger.info(f"Keyword blocked: {keyword}")
                self._cache_valid = False
                return True
        except Exception as e:
            logger.error(f"Error adding blocked keyword: {e}")
            return False
    
    def is_url_blocked(self, url: str) -> Tuple[bool, Optional[str]]:
        """
        Check if URL is blocked
        
        Args:
            url: URL to check
        
        Returns:
            Tuple of (is_blocked: bool, reason: Optional[str])
        """
        if not self._cache_valid:
            self.refresh_filters()
        
        url_lower = url.lower()
        
        # Check against blocked domains
        for domain in self._blocked_domains_cache:
            if domain.lower() in url_lower:
                return True, f"Blocked domain: {domain}"
        
        # Check against blocked keywords
        for keyword in self._blocked_keywords_cache:
            # Simple keyword matching by default
            if keyword.lower() in url_lower:
                return True, f"Blocked keyword: {keyword}"
        
        return False, None
    
    def get_all_blocked_domains(self) -> List[Dict]:
        """Get all blocked domains with details"""
        try:
            with Database.session_context() as session:
                domains = session.query(BlockedDomain).all()
                return [d.to_dict() for d in domains]
        except Exception as e:
            logger.error(f"Error getting blocked domains: {e}")
            return []
    
    def get_all_blocked_keywords(self) -> List[Dict]:
        """Get all blocked keywords with details"""
        try:
            with Database.session_context() as session:
                keywords = session.query(BlockedKeyword).all()
                return [k.to_dict() for k in keywords]
        except Exception as e:
            logger.error(f"Error getting blocked keywords: {e}")
            return []


# Global filter engine instance
filter_engine = FilterEngine()
