"""
Tests for queue management
"""

import pytest
from quetie.queue.manager import queue_manager
from quetie.db.database import Database
from quetie.db.models import QueueEntry, QueueEntryStatus


class TestQueueManager:
    """Test QueueManager functionality"""
    
    @classmethod
    def setup_class(cls):
        """Setup test database"""
        Database.initialize("sqlite:///:memory:")
    
    def test_add_to_queue_valid(self):
        """Test adding valid URL to queue"""
        success, message, entry_id = queue_manager.add_to_queue(
            url="https://example.com/video",
            submitter_username="test_user"
        )
        
        assert success
        assert entry_id is not None
        assert "queue" in message.lower()
    
    def test_add_to_queue_invalid_url(self):
        """Test adding invalid URL to queue"""
        success, message, entry_id = queue_manager.add_to_queue(
            url="not-a-url",
            submitter_username="test_user"
        )
        
        assert not success
        assert entry_id is None
        assert "invalid" in message.lower()
    
    def test_add_to_queue_empty_url(self):
        """Test adding empty URL"""
        success, message, entry_id = queue_manager.add_to_queue(
            url="",
            submitter_username="test_user"
        )
        
        assert not success
        assert entry_id is None
    
    def test_duplicate_detection(self):
        """Test duplicate URL detection"""
        url = "https://example.com/duplicate-test"
        
        # Add first time
        success1, message1, entry_id1 = queue_manager.add_to_queue(
            url=url,
            submitter_username="user1"
        )
        assert success1
        
        # Try to add duplicate
        success2, message2, entry_id2 = queue_manager.add_to_queue(
            url=url,
            submitter_username="user2"
        )
        assert not success2
        assert "duplicate" in message2.lower() or "already" in message2.lower()
    
    def test_blocked_domain_rejection(self):
        """Test rejection of URLs with blocked domains"""
        from quetie.filtering.filters import filter_engine
        
        # Add blocked domain
        filter_engine.add_blocked_domain("blocked-domain.com")
        
        success, message, entry_id = queue_manager.add_to_queue(
            url="https://blocked-domain.com/content",
            submitter_username="test_user"
        )
        
        assert not success
        assert "blocked" in message.lower() or "rejected" in message.lower()
        
        # Clean up
        filter_engine.remove_blocked_domain("blocked-domain.com")
    
    def test_get_queue(self):
        """Test retrieving queue"""
        # Add test entries
        queue_manager.add_to_queue("https://test1.com", "user1")
        queue_manager.add_to_queue("https://test2.com", "user2")
        
        entries, total = queue_manager.get_queue(limit=10)
        
        assert len(entries) > 0
        assert total >= 2
    
    def test_mark_as_playing(self):
        """Test marking entry as playing"""
        success, message, entry_id = queue_manager.add_to_queue(
            url="https://playing-test.com",
            submitter_username="test_user"
        )
        
        if success and entry_id:
            play_success, play_message = queue_manager.mark_as_playing(entry_id)
            assert play_success
    
    def test_mark_as_completed(self):
        """Test marking entry as completed"""
        success, message, entry_id = queue_manager.add_to_queue(
            url="https://complete-test.com",
            submitter_username="test_user"
        )
        
        if success and entry_id:
            complete_success, complete_message = queue_manager.mark_as_completed(entry_id)
            assert complete_success
    
    def test_remove_from_queue(self):
        """Test removing entry from queue"""
        success, message, entry_id = queue_manager.add_to_queue(
            url="https://remove-test.com",
            submitter_username="test_user"
        )
        
        if success and entry_id:
            remove_success, remove_message = queue_manager.remove_from_queue(
                entry_id,
                reason="Test removal"
            )
            assert remove_success
    
    def test_search_queue(self):
        """Test searching queue"""
        queue_manager.add_to_queue("https://search-test.com", "searchuser")
        
        results = queue_manager.search_queue("search")
        assert len(results) > 0
    
    def test_get_statistics(self):
        """Test getting queue statistics"""
        stats = queue_manager.get_statistics()
        
        assert stats is not None
        assert "total_links_submitted" in stats
        assert "total_links_accepted" in stats


if __name__ == "__main__":
    pytest.main([__file__])
