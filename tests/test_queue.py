"""
Tests for queue management
"""

import pytest
from datetime import timedelta
from quetie.queue.manager import queue_manager
from quetie.queue.manager import QueueManager
from quetie.db.database import Database
from quetie.db.models import QueueEntry, QueueEntryStatus, AppSetting
from quetie.config.settings import settings
from quetie.utils.time import utc_now_iso, utc_now


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

    def test_mark_as_playing_replaces_previous_current_entry(self):
        """Test only one queue entry remains in playing state at a time"""
        first_success, _, first_id = queue_manager.add_to_queue(
            url="https://queue-first-example.com/watch",
            submitter_username="test_user"
        )
        second_success, _, second_id = queue_manager.add_to_queue(
            url="https://queue-second-example.com/watch",
            submitter_username="test_user"
        )

        assert first_success and first_id is not None
        assert second_success and second_id is not None

        first_play_success, _, _ = queue_manager.mark_as_playing(first_id)
        second_play_success, _, _ = queue_manager.mark_as_playing(second_id)

        assert first_play_success
        assert second_play_success

        current = queue_manager.get_current_playing()
        assert current is not None
        assert current["id"] == second_id

        entries, _ = queue_manager.get_queue(limit=50)
        first_entry = next((entry for entry in entries if entry["id"] == first_id), None)
        assert first_entry is not None
        assert first_entry["status"] == QueueEntryStatus.PENDING.value

    def test_get_current_playing(self):
        """Test retrieving the current playing queue entry"""
        success, message, entry_id = queue_manager.add_to_queue(
            url="https://current-playing-test.com",
            submitter_username="test_user"
        )

        if success and entry_id:
            queue_manager.mark_as_playing(entry_id)
            current = queue_manager.get_current_playing()
            assert current is not None
            assert current["id"] == entry_id
    
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
        queue_manager.add_to_queue("https://valid-test-domain.com", "searchuser")
        
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


def test_restore_runtime_state_preserves_current_playing_after_restart():
    Database.initialize("sqlite:///:memory:")
    manager = QueueManager()

    success, _, entry_id = manager.add_to_queue(
        url="https://restore-example.com/video.mp4",
        submitter_username="restore_user",
    )
    assert success and entry_id is not None

    play_success, _, _ = manager.mark_as_playing(entry_id)
    assert play_success

    restored_manager = QueueManager()
    state = restored_manager.restore_runtime_state()

    assert state["playing_entry_id"] == entry_id
    current = restored_manager.get_current_playing()
    assert current is not None
    assert current["id"] == entry_id
    assert restored_manager.get_playback_state()["current_entry_id"] == entry_id


def test_restore_runtime_state_repairs_multiple_playing_rows():
    Database.initialize("sqlite:///:memory:")
    manager = QueueManager()

    success1, _, first_id = manager.add_to_queue(
        url="https://repair-example.com/one",
        submitter_username="repair_user",
    )
    success2, _, second_id = manager.add_to_queue(
        url="https://repair-example.com/two",
        submitter_username="repair_user",
    )
    assert success1 and first_id is not None
    assert success2 and second_id is not None

    with Database.session_context() as session:
        first = session.query(QueueEntry).filter(QueueEntry.id == first_id).first()
        second = session.query(QueueEntry).filter(QueueEntry.id == second_id).first()
        first.status = QueueEntryStatus.PLAYING
        second.status = QueueEntryStatus.PLAYING

    repaired = manager.restore_runtime_state()
    assert repaired["playing_entry_id"] in {first_id, second_id}

    with Database.session_context() as session:
        playing_entries = session.query(QueueEntry).filter(
            QueueEntry.status == QueueEntryStatus.PLAYING
        ).all()
        assert len(playing_entries) == 1


def test_restore_runtime_state_removes_invalid_active_entries():
    Database.initialize("sqlite:///:memory:")
    manager = QueueManager()

    with Database.session_context() as session:
        session.add(
            QueueEntry(
                url="not-a-valid-url",
                status=QueueEntryStatus.PLAYING,
                submitter_username="broken_user",
                position=0,
            )
        )

    repaired = manager.restore_runtime_state()
    assert repaired["playing_entry_id"] is None
    assert manager.get_current_playing() is None


def test_restore_runtime_state_clears_stale_playing_state():
    Database.initialize("sqlite:///:memory:")
    manager = QueueManager()

    success, _, entry_id = manager.add_to_queue(
        url="https://stale-example.com/video.mp4",
        submitter_username="stale_user",
    )
    assert success and entry_id is not None

    play_success, _, _ = manager.mark_as_playing(entry_id)
    assert play_success

    with Database.session_context() as session:
        setting = session.query(AppSetting).filter(AppSetting.key == QueueManager.PLAYBACK_STATE_KEY).first()
        assert setting is not None
        stale_started_at = (utc_now() - timedelta(seconds=settings.PLAYING_STALE_AFTER_SECONDS + 5)).isoformat()
        setting.value = f'''{{
            "current_entry_id": {entry_id},
            "current_url": "https://stale-example.com/video.mp4",
            "status": "playing",
            "reason": "manual_test",
            "updated_at": "{utc_now_iso()}",
            "started_at": "{stale_started_at}"
        }}'''

    restored = manager.restore_runtime_state()
    assert restored["playing_entry_id"] is None

    current = manager.get_current_playing()
    assert current is None

    with Database.session_context() as session:
        playing_rows = session.query(QueueEntry).filter(QueueEntry.status == QueueEntryStatus.PLAYING).all()
        assert len(playing_rows) == 0
