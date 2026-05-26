"""
Link validation for Quetie_mbg
Validates URLs, detects malformed links, and checks against blocked domains
"""

import re
from urllib.parse import urlparse
from typing import Tuple, Optional
from quetie.utils.logger import setup_logger

logger = setup_logger(__name__)


class LinkValidator:
    """Validates and analyzes links for queue submission"""
    
    # URL pattern - matches http/https URLs
    URL_PATTERN = re.compile(
        r'^https?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain
        r'localhost|'  # localhost
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # IP
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$',
        re.IGNORECASE
    )
    
    @staticmethod
    def is_valid_url(url: str) -> bool:
        """
        Check if URL matches basic URL pattern
        
        Args:
            url: URL to validate
        
        Returns:
            True if URL is valid format, False otherwise
        """
        if not url or not isinstance(url, str):
            return False
        
        url = url.strip()
        
        # Check length
        if len(url) > 2048:
            logger.warning(f"URL exceeds maximum length: {len(url)}")
            return False
        
        # Check pattern
        if not LinkValidator.URL_PATTERN.match(url):
            logger.debug(f"URL failed pattern validation: {url}")
            return False
        
        return True
    
    @staticmethod
    def extract_domain(url: str) -> Optional[str]:
        """
        Extract domain from URL
        
        Args:
            url: URL to parse
        
        Returns:
            Domain name or None if invalid
        """
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            # Remove port if present
            if ':' in domain:
                domain = domain.split(':')[0]
            return domain
        except Exception as e:
            logger.error(f"Error parsing domain from URL: {e}")
            return None

    @staticmethod
    def derive_display_title(url: str) -> str:
        """
        Derive a short display title from a URL.

        Args:
            url: URL to analyze

        Returns:
            Human-friendly title for queue display
        """
        try:
            parsed = urlparse(url)
            path_parts = [part for part in parsed.path.split('/') if part]

            if path_parts:
                candidate = path_parts[-1].replace('-', ' ').replace('_', ' ')
                candidate = re.sub(r'\s+', ' ', candidate).strip()
                if candidate:
                    return candidate[:80]

            domain = LinkValidator.extract_domain(url)
            if domain:
                return domain
        except Exception:
            pass

        return url[:80]
    
    @staticmethod
    def is_discord_link(url: str) -> bool:
        """Check if URL is a Discord invite or server link"""
        domain = LinkValidator.extract_domain(url)
        if not domain:
            return False
        
        discord_patterns = [
            "discord.gg",
            "discord.com",
            "discordapp.com",
        ]
        
        return any(pattern in domain for pattern in discord_patterns)
    
    @staticmethod
    def is_social_media_link(url: str) -> bool:
        """Check if URL is a social media self-promotion link"""
        domain = LinkValidator.extract_domain(url)
        if not domain:
            return False
        
        social_patterns = [
            "twitter.com",
            "x.com",
            "instagram.com",
            "tiktok.com",
            "facebook.com",
            "reddit.com",
        ]
        
        return any(pattern in domain for pattern in social_patterns)
    
    @staticmethod
    def is_nightbot_link(url: str) -> bool:
        """Check if URL is a Nightbot or similar bot link"""
        domain = LinkValidator.extract_domain(url)
        if not domain:
            return False
        
        bot_patterns = [
            "nightbot.tv",
            "nightbot.com",
            "streamelements.com",
            "botfarm.io",
        ]
        
        return any(pattern in domain for pattern in bot_patterns)
    
    @staticmethod
    def is_short_url(url: str) -> bool:
        """Check if URL is a shortened URL"""
        domain = LinkValidator.extract_domain(url)
        if not domain:
            return False
        
        short_patterns = [
            "bit.ly",
            "tinyurl.com",
            "short.link",
            "ow.ly",
            "shortened.link",
        ]
        
        return any(pattern in domain for pattern in short_patterns)
    
    @staticmethod
    def validate_url(
        url: str,
        blocked_domains: list = None,
        blocked_keywords: list = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Comprehensive URL validation
        
        Args:
            url: URL to validate
            blocked_domains: List of blocked domains
            blocked_keywords: List of blocked keywords/patterns
        
        Returns:
            Tuple of (is_valid: bool, reason: Optional[str])
            If invalid, reason explains why
        """
        if not url:
            return False, "Empty URL"
        
        url = url.strip()
        
        # Check basic format
        if not LinkValidator.is_valid_url(url):
            return False, "Invalid URL format"

        # Check specific blocked types
        if LinkValidator.is_discord_link(url):
            return False, "Discord links not allowed"
        
        if LinkValidator.is_nightbot_link(url):
            return False, "Bot service links not allowed"
        
        # Check blocked domains
        domain = LinkValidator.extract_domain(url)
        if blocked_domains:
            for blocked_domain in blocked_domains:
                if blocked_domain.lower() in url.lower():
                    return False, f"Domain blocked: {blocked_domain}"
        
        # Check blocked keywords
        if blocked_keywords:
            for keyword in blocked_keywords:
                if keyword.lower() in url.lower():
                    return False, f"Content contains blocked keyword: {keyword}"
        
        return True, None
    
    @staticmethod
    def sanitize_url(url: str) -> str:
        """
        Sanitize URL for safe storage
        
        Args:
            url: URL to sanitize
        
        Returns:
            Sanitized URL
        """
        if not url:
            return ""
        
        url = url.strip()
        
        # Remove common tracking parameters
        tracking_params = [
            "utm_source",
            "utm_medium",
            "utm_campaign",
            "fbclid",
            "gclid",
        ]
        
        parsed = urlparse(url)
        if parsed.query:
            params = parsed.query.split("&")
            filtered_params = [
                p for p in params
                if not any(p.startswith(tp + "=") for tp in tracking_params)
            ]
            if filtered_params:
                return f"{parsed.scheme}://{parsed.netloc}{parsed.path}?{'&'.join(filtered_params)}"
            else:
                return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        
        return url
