"""
Tests for link validation and filtering
"""

import pytest
from quetie.filtering.validators import LinkValidator
from quetie.filtering.filters import filter_engine


class TestLinkValidator:
    """Test LinkValidator functionality"""
    
    def test_valid_url_formats(self):
        """Test validation of valid URL formats"""
        valid_urls = [
            "http://example.com",
            "https://example.com/path",
            "https://youtube.com/watch?v=dQw4w9WgXcQ",
            "https://example.com:8080/path",
            "http://localhost:3000",
            "https://api.example.com/v1/resource",
        ]
        
        for url in valid_urls:
            assert LinkValidator.is_valid_url(url), f"Failed for: {url}"
    
    def test_invalid_url_formats(self):
        """Test validation of invalid URL formats"""
        invalid_urls = [
            "not-a-url",
            "example.com",
            "ftp://example.com",
            "/path/only",
            "",
            None,
            "http://",
            "https://",
        ]
        
        for url in invalid_urls:
            assert not LinkValidator.is_valid_url(url), f"Should fail for: {url}"
    
    def test_url_length_validation(self):
        """Test URL length validation"""
        long_url = "http://example.com/" + "a" * 2100
        assert not LinkValidator.is_valid_url(long_url)
    
    def test_discord_link_detection(self):
        """Test Discord link detection"""
        discord_urls = [
            "https://discord.gg/invite",
            "https://discord.com/channels",
            "https://discordapp.com",
        ]
        
        for url in discord_urls:
            assert LinkValidator.is_discord_link(url), f"Failed for: {url}"
    
    def test_social_media_link_detection(self):
        """Test social media link detection"""
        social_urls = [
            "https://twitter.com/user",
            "https://instagram.com/user",
        ]
        
        for url in social_urls:
            assert LinkValidator.is_social_media_link(url), f"Failed for: {url}"

    def test_twitch_links_are_not_blocked_as_social(self):
        """Twitch URLs should be queueable links, not social-media rejections."""
        twitch_urls = [
            "https://twitch.tv/example",
            "https://clips.twitch.tv/example",
        ]

        for url in twitch_urls:
            assert not LinkValidator.is_social_media_link(url), f"Should allow: {url}"

        is_valid, reason = LinkValidator.validate_url("https://twitch.tv/example")
        assert is_valid
        assert reason is None
    
    def test_domain_extraction(self):
        """Test domain extraction from URLs"""
        test_cases = [
            ("https://example.com/path", "example.com"),
            ("http://sub.example.com:8080/path", "sub.example.com"),
            ("https://youtube.com?v=test", "youtube.com"),
        ]
        
        for url, expected_domain in test_cases:
            domain = LinkValidator.extract_domain(url)
            assert domain == expected_domain, f"Failed for: {url}"
    
    def test_url_validation_with_filters(self):
        """Test comprehensive URL validation"""
        # Valid URL
        is_valid, reason = LinkValidator.validate_url("https://example.com")
        assert is_valid
        assert reason is None

        # Discord URL
        is_valid, reason = LinkValidator.validate_url("https://discord.gg/invite")
        assert not is_valid
        assert "Discord" in reason
        # URL with blocked domain
        is_valid, reason = LinkValidator.validate_url(
            "https://example.com",
            blocked_domains=["example.com"]
        )
        assert not is_valid
        assert "blocked" in reason.lower()
    
    def test_url_sanitization(self):
        """Test URL sanitization"""
        url_with_tracking = "https://example.com/path?utm_source=test&id=123&utm_campaign=camp"
        sanitized = LinkValidator.sanitize_url(url_with_tracking)
        
        # Should remove tracking params but keep others
        assert "utm_source" not in sanitized
        assert "id=123" in sanitized


class TestFilterEngine:
    """Test FilterEngine functionality"""
    
    def test_filter_engine_initialization(self):
        """Test filter engine initialization"""
        engine = filter_engine
        assert engine is not None
    
    def test_blocked_domain_management(self):
        """Test adding and removing blocked domains"""
        engine = filter_engine
        
        # Add domain
        success = engine.add_blocked_domain("spam.com", "Test spam domain")
        assert success
        
        # Check if blocked
        is_blocked, reason = engine.is_url_blocked("https://spam.com/page")
        assert is_blocked
        assert "spam.com" in reason
        
        # Remove domain
        success = engine.remove_blocked_domain("spam.com")
        assert success
    
    def test_url_blocking(self):
        """Test URL blocking"""
        engine = filter_engine
        
        # Add test domain
        engine.add_blocked_domain("test-blocked.com")
        
        # Test blocking
        is_blocked, reason = engine.is_url_blocked("https://test-blocked.com/content")
        assert is_blocked
        
        # Clean up
        engine.remove_blocked_domain("test-blocked.com")

if __name__ == "__main__":
    pytest.main([__file__])
