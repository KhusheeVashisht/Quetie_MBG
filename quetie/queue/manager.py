"""
Queue management for Quetie_mbg
Core queue operations: add, remove, reorder, track status
"""

import json
from datetime import datetime, timedelta, UTC
from typing import List, Dict, Optional, Tuple
from sqlalchemy import desc
from quetie.db.database import Database
from quetie.db.models import QueueEntry, QueueEntryStatus, BotStatistic, AppSetting
from quetie.filtering.validators import LinkValidator
from quetie.filtering.filters import filter_engine
from quetie.config.settings import settings
from quetie.utils.logger import setup_logger
from quetie.utils.diagnostics import record_diagnostic
from quetie.utils.time import utc_now, utc_now_iso

logger = setup_logger(__name__)


class QueueManager:
    """Manages queue operations and persistence"""

    PLAYBACK_STATE_KEY = "playback_state"
    
    def __init__(self):
        """Initialize queue manager"""
        self._duplicate_cache = set()
        self._refresh_duplicate_cache()
    
    def _refresh_duplicate_cache(self) -> None:
        """Refresh cache of URLs already in queue"""
        try:
            with Database.session_context() as session:
                pending_urls = session.query(QueueEntry.url).filter(
                    QueueEntry.status.in_([QueueEntryStatus.PENDING, QueueEntryStatus.PLAYING])
                ).all()
                self._duplicate_cache = set(url[0].lower() for url in pending_urls)
                logger.debug(f"Duplicate cache refreshed: {len(self._duplicate_cache)} URLs")
        except Exception as e:
            logger.error(f"Error refreshing duplicate cache: {e}")
            self._duplicate_cache = set()

    def _get_runtime_setting(self, key: str, default):
        """Read a runtime setting from the database with a fallback."""
        try:
            with Database.session_context() as session:
                setting = session.query(AppSetting).filter(AppSetting.key == key).first()
                if not setting:
                    return default
                return json.loads(setting.value)
        except Exception as e:
            logger.debug(f"Using default for runtime setting {key}: {e}")
            return default

    def _set_runtime_setting(self, session, key: str, value) -> None:
        setting = session.query(AppSetting).filter(AppSetting.key == key).first()
        serialized = json.dumps(value)
        if setting:
            setting.value = serialized
        else:
            session.add(AppSetting(key=key, value=serialized))

    def _normalize_pending_positions(self, session) -> None:
        entries = session.query(QueueEntry).filter(
            QueueEntry.status == QueueEntryStatus.PENDING
        ).order_by(QueueEntry.position.asc(), QueueEntry.created_at.asc(), QueueEntry.id.asc()).all()
        for index, entry in enumerate(entries):
            entry.position = index

    def _persist_playback_state(self, session, *, current_entry: Optional[QueueEntry], status: str, reason: str) -> None:
        payload = {
            "current_entry_id": current_entry.id if current_entry else None,
            "current_url": current_entry.url if current_entry else None,
            "status": status,
            "reason": reason,
            "updated_at": utc_now_iso(),
        }
        if current_entry:
            payload["started_at"] = utc_now_iso()
        self._set_runtime_setting(session, self.PLAYBACK_STATE_KEY, payload)

    def _mark_playing_entries_pending(self, session) -> None:
        session.query(QueueEntry).filter(
            QueueEntry.status == QueueEntryStatus.PLAYING
        ).update({QueueEntry.status: QueueEntryStatus.PENDING}, synchronize_session=False)

    def _is_playback_stale(self, playback_state: Dict) -> bool:
        started_at = playback_state.get("started_at")
        if not started_at:
            return False
        try:
            started = datetime.fromisoformat(started_at)
            if started.tzinfo is None:
                started = started.replace(tzinfo=UTC)
        except Exception:
            return False
        stale_after = getattr(settings, "PLAYING_STALE_AFTER_SECONDS", 21600)
        return utc_now() - started > timedelta(seconds=stale_after)

    def get_playback_state(self) -> Dict:
        return self._get_runtime_setting(
            self.PLAYBACK_STATE_KEY,
            {
                "current_entry_id": None,
                "current_url": None,
                "status": "idle",
                "reason": "startup",
                "updated_at": None,
            },
        )

    def restore_runtime_state(self) -> Dict:
        """Repair queue consistency and preserve persisted playback state across restarts."""
        try:
            with Database.session_context() as session:
                active_entries = session.query(QueueEntry).filter(
                    QueueEntry.status.in_([QueueEntryStatus.PENDING, QueueEntryStatus.PLAYING])
                ).all()
                for entry in active_entries:
                    if LinkValidator.is_valid_url(entry.url):
                        continue
                    entry.status = QueueEntryStatus.REMOVED
                    entry.removed_at = utc_now()
                    entry.notes = (entry.notes or "") + " [auto-removed during state restore]"
                session.flush()

                self._normalize_pending_positions(session)

                playing_entries = session.query(QueueEntry).filter(
                    QueueEntry.status == QueueEntryStatus.PLAYING
                ).order_by(QueueEntry.created_at.asc(), QueueEntry.id.asc()).all()

                playback_state = self.get_playback_state()
                preferred_id = playback_state.get("current_entry_id")
                survivor = None

                stale_playback = self._is_playback_stale(playback_state)
                if stale_playback:
                    logger.warning("Stale playback detected; clearing playing state")
                    self._mark_playing_entries_pending(session)
                    playing_entries = []
                    preferred_id = None

                if playing_entries:
                    survivor = next((entry for entry in playing_entries if entry.id == preferred_id), None)
                    if survivor is None:
                        survivor = playing_entries[0]

                for entry in playing_entries:
                    if survivor and entry.id == survivor.id:
                        continue
                    entry.status = QueueEntryStatus.PENDING

                if survivor:
                    self._persist_playback_state(
                        session,
                        current_entry=survivor,
                        status="playing",
                        reason="restored_after_restart",
                    )
                else:
                    self._persist_playback_state(
                        session,
                        current_entry=None,
                        status="idle",
                        reason="no_active_playback",
                    )

                self._normalize_pending_positions(session)
                self._refresh_duplicate_cache()

                payload = {
                    "playing_entry_id": survivor.id if survivor else None,
                    "pending_count": session.query(QueueEntry).filter(
                        QueueEntry.status == QueueEntryStatus.PENDING
                    ).count(),
                }
                record_diagnostic("queue", "state_restored", **payload)
                logger.info(
                    "queue_state_restored playing_entry_id=%s pending_count=%s",
                    payload["playing_entry_id"],
                    payload["pending_count"],
                )
                return payload
        except Exception as e:
            logger.error(f"Error restoring runtime state: {e}")
            record_diagnostic("queue", "state_restore_failed", level="ERROR", error=str(e))
            return {"playing_entry_id": None, "pending_count": 0, "error": str(e)}
    
    def add_to_queue(
        self,
        url: str,
        submitter_username: str,
        notes: str = None
    ) -> Tuple[bool, str, Optional[int]]:
        """
        Add a link to the queue with full validation
        
        Args:
            url: URL to add
            submitter_username: Username of submitter
            notes: Optional notes about the submission
        
        Returns:
            Tuple of (success: bool, message: str, queue_entry_id: Optional[int])
        """
        if not url or not submitter_username:
            return False, "Missing URL or submitter username", None
        
        url = url.strip()
        
        # Validate URL format
        if not LinkValidator.is_valid_url(url):
            return False, "Invalid URL format", None
        
        # Sanitize URL
        sanitized_url = LinkValidator.sanitize_url(url)
        
        # Check for duplicates
        if sanitized_url.lower() in self._duplicate_cache:
            logger.warning(f"Duplicate URL submission: {sanitized_url} from {submitter_username}")
            return False, "This link is already in the queue", None
        
        # Check against blocked domains/keywords
        is_blocked, block_reason = filter_engine.is_url_blocked(sanitized_url)
        if is_blocked:
            logger.warning(f"Blocked URL submission: {sanitized_url} - {block_reason}")
            return False, f"Link rejected: {block_reason}", None
        
        # Check queue size
        current_size = self._get_queue_size()
        max_queue_size = self._get_runtime_setting("max_queue_size", settings.MAX_QUEUE_SIZE)
        if current_size >= max_queue_size:
            logger.warning(f"Queue is full ({current_size}/{max_queue_size})")
            return False, "Queue is full, try again later", None
        
        # Add to database
        try:
            with Database.session_context() as session:
                # Get next position
                next_position = session.query(QueueEntry).filter(
                    QueueEntry.status == QueueEntryStatus.PENDING
                ).count()
                
                queue_entry = QueueEntry(
                    url=sanitized_url,
                    status=QueueEntryStatus.PENDING,
                    submitter_username=submitter_username,
                    position=next_position,
                    notes=notes
                )
                session.add(queue_entry)
                
                # Update statistics
                stat = session.query(BotStatistic).first()
                if stat:
                    stat.total_links_submitted += 1
                    stat.total_links_accepted += 1
                else:
                    stat = BotStatistic(
                        total_links_submitted=1,
                        total_links_accepted=1
                    )
                    session.add(stat)
                
                session.commit()
                
                # Update cache
                self._refresh_duplicate_cache()
                
                logger.info(f"Added to queue: {sanitized_url} from {submitter_username}")
                record_diagnostic(
                    "queue",
                    "entry_added",
                    entry_id=queue_entry.id,
                    submitter=submitter_username,
                    url=sanitized_url,
                    position=next_position,
                )
                return True, f"Added to queue (position {next_position + 1})", queue_entry.id
        
        except Exception as e:
            logger.error(f"Error adding to queue: {e}")
            return False, "Server error while adding to queue", None
    
    def get_queue(self, limit: int = 50, offset: int = 0) -> Tuple[List[Dict], int]:
        """
        Get pending queue entries
        
        Args:
            limit: Maximum number of entries to return
            offset: Number of entries to skip
        
        Returns:
            Tuple of (entries: List[Dict], total_count: int)
        """
        try:
            with Database.session_context() as session:
                # Get total count
                total = session.query(QueueEntry).filter(
                    QueueEntry.status == QueueEntryStatus.PENDING
                ).count()
                
                # Get entries
                entries = session.query(QueueEntry).filter(
                    QueueEntry.status == QueueEntryStatus.PENDING
                ).order_by(QueueEntry.position).limit(limit).offset(offset).all()
                
                return [e.to_dict() for e in entries], total
        except Exception as e:
            logger.error(f"Error getting queue: {e}")
            return [], 0

    def get_current_playing(self) -> Optional[Dict]:
        """Get the currently playing queue entry, if any."""
        try:
            with Database.session_context() as session:
                entry = session.query(QueueEntry).filter(
                    QueueEntry.status == QueueEntryStatus.PLAYING
                ).order_by(QueueEntry.created_at.asc()).first()

                return entry.to_dict() if entry else None
        except Exception as e:
            logger.error(f"Error getting current playing entry: {e}")
            return None
    
    def mark_as_playing(self, queue_entry_id: int) -> Tuple[bool, str, Optional[str]]:
        """
        Mark a queue entry as currently playing
        
        Args:
            queue_entry_id: ID of queue entry
        
        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            with Database.session_context() as session:
                entry = session.query(QueueEntry).filter(
                    QueueEntry.id == queue_entry_id
                ).first()
                
                if not entry:
                    return False, "Queue entry not found"

                session.query(QueueEntry).filter(
                    QueueEntry.status == QueueEntryStatus.PLAYING,
                    QueueEntry.id != queue_entry_id
                ).update(
                    {QueueEntry.status: QueueEntryStatus.PENDING},
                    synchronize_session=False
                )
                
                entry.status = QueueEntryStatus.PLAYING
                self._normalize_pending_positions(session)
                self._persist_playback_state(
                    session,
                    current_entry=entry,
                    status="playing",
                    reason="manual_or_autoplay_start",
                )
                session.commit()
                self._refresh_duplicate_cache()
                logger.info(f"Marked as playing: {queue_entry_id}")
                record_diagnostic("queue", "entry_playing", entry_id=queue_entry_id, url=entry.url)
                return True, f"Now playing: {entry.url}", entry.url
        except Exception as e:
            logger.error(f"Error marking as playing: {e}")
            record_diagnostic("queue", "entry_playing_failed", level="ERROR", entry_id=queue_entry_id, error=str(e))
        return False, "Server error", None
    
    def mark_as_completed(self, queue_entry_id: int) -> Tuple[bool, str]:
        """
        Mark a queue entry as completed
        
        Args:
            queue_entry_id: ID of queue entry
        
        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            with Database.session_context() as session:
                entry = session.query(QueueEntry).filter(
                    QueueEntry.id == queue_entry_id
                ).first()
                
                if not entry:
                    return False, "Queue entry not found"
                
                entry.status = QueueEntryStatus.COMPLETED
                entry.played_at = utc_now()
                
                # Update statistics
                stat = session.query(BotStatistic).first()
                if stat:
                    stat.total_links_played += 1

                self._persist_playback_state(
                    session,
                    current_entry=None,
                    status="completed",
                    reason=f"completed_entry_{queue_entry_id}",
                )
                self._normalize_pending_positions(session)
                session.commit()
                self._refresh_duplicate_cache()
                logger.info(f"Marked as completed: {queue_entry_id}")
                record_diagnostic("queue", "entry_completed", entry_id=queue_entry_id)
                return True, "Entry marked as completed"
        except Exception as e:
            logger.error(f"Error marking as completed: {e}")
            record_diagnostic("queue", "entry_completed_failed", level="ERROR", entry_id=queue_entry_id, error=str(e))
            return False, "Server error"
    
    def remove_from_queue(self, queue_entry_id: int, reason: str = None) -> Tuple[bool, str]:
        """
        Remove a queue entry
        
        Args:
            queue_entry_id: ID of queue entry
            reason: Reason for removal
        
        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            with Database.session_context() as session:
                entry = session.query(QueueEntry).filter(
                    QueueEntry.id == queue_entry_id
                ).first()
                
                if not entry:
                    return False, "Queue entry not found"
                
                entry.status = QueueEntryStatus.REMOVED
                entry.removed_at = utc_now()
                entry.notes = reason or entry.notes
                
                # Update statistics
                stat = session.query(BotStatistic).first()
                if stat:
                    stat.total_links_rejected += 1

                playback_state = self.get_playback_state()
                if playback_state.get("current_entry_id") == queue_entry_id:
                    self._persist_playback_state(
                        session,
                        current_entry=None,
                        status="removed",
                        reason=f"removed_entry_{queue_entry_id}",
                    )

                self._normalize_pending_positions(session)
                session.commit()
                self._refresh_duplicate_cache()
                logger.info(f"Removed from queue: {queue_entry_id}")
                record_diagnostic("queue", "entry_removed", entry_id=queue_entry_id, reason=reason or "")
                return True, "Entry removed"
        except Exception as e:
            logger.error(f"Error removing from queue: {e}")
            record_diagnostic("queue", "entry_removed_failed", level="ERROR", entry_id=queue_entry_id, error=str(e))
            return False, "Server error"
    
    def reorder_queue(self, order: List[int]) -> Tuple[bool, str]:
        """
        Reorder queue entries by IDs
        
        Args:
            order: List of queue entry IDs in desired order
        
        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            with Database.session_context() as session:
                for position, entry_id in enumerate(order):
                    entry = session.query(QueueEntry).filter(
                        QueueEntry.id == entry_id,
                        QueueEntry.status == QueueEntryStatus.PENDING,
                    ).first()
                    
                    if entry:
                        entry.position = position
                
                session.commit()
                logger.info(f"Queue reordered: {len(order)} entries")
                record_diagnostic("queue", "queue_reordered", entry_count=len(order))
                return True, "Queue reordered successfully"
        except Exception as e:
            logger.error(f"Error reordering queue: {e}")
            record_diagnostic("queue", "queue_reordered_failed", level="ERROR", error=str(e))
            return False, "Server error"
    
    def search_queue(self, query: str, limit: int = 50) -> List[Dict]:
        """
        Search queue entries by URL or submitter
        
        Args:
            query: Search query
            limit: Maximum results
        
        Returns:
            List of matching entries
        """
        try:
            with Database.session_context() as session:
                entries = session.query(QueueEntry).filter(
                    (QueueEntry.url.ilike(f"%{query}%")) |
                    (QueueEntry.submitter_username.ilike(f"%{query}%")),
                    QueueEntry.status == QueueEntryStatus.PENDING
                ).limit(limit).all()
                
                return [e.to_dict() for e in entries]
        except Exception as e:
            logger.error(f"Error searching queue: {e}")
            return []
    
    def _get_queue_size(self) -> int:
        """Get current queue size"""
        try:
            with Database.session_context() as session:
                return session.query(QueueEntry).filter(
                    QueueEntry.status == QueueEntryStatus.PENDING
                ).count()
        except Exception as e:
            logger.error(f"Error getting queue size: {e}")
            return 0
    
    def get_statistics(self) -> Dict:
        """Get queue statistics"""
        try:
            with Database.session_context() as session:
                stat = session.query(BotStatistic).first()
                if stat:
                    return stat.to_dict()
                return {
                    "total_links_submitted": 0,
                    "total_links_accepted": 0,
                    "total_links_rejected": 0,
                    "total_links_played": 0,
                }
        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            return {}


# Global queue manager instance
queue_manager = QueueManager()
