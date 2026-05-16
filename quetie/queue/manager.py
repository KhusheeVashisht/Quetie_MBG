"""
Queue management for Quetie_mbg
Core queue operations: add, remove, reorder, track status
"""

from datetime import datetime
from typing import List, Dict, Optional, Tuple
from sqlalchemy import desc
from quetie.db.database import Database
from quetie.db.models import QueueEntry, QueueEntryStatus, BotStatistic
from quetie.filtering.validators import LinkValidator
from quetie.filtering.filters import filter_engine
from quetie.config.settings import settings
from quetie.utils.logger import setup_logger

logger = setup_logger(__name__)


class QueueManager:
    """Manages queue operations and persistence"""
    
    def __init__(self):
        """Initialize queue manager"""
        self._duplicate_cache = set()
        self._refresh_duplicate_cache()
    
    def _refresh_duplicate_cache(self) -> None:
        """Refresh cache of URLs already in queue"""
        try:
            with Database.session_context() as session:
                pending_urls = session.query(QueueEntry.url).filter(
                    QueueEntry.status == QueueEntryStatus.PENDING
                ).all()
                self._duplicate_cache = set(url[0].lower() for url in pending_urls)
                logger.debug(f"Duplicate cache refreshed: {len(self._duplicate_cache)} URLs")
        except Exception as e:
            logger.error(f"Error refreshing duplicate cache: {e}")
            self._duplicate_cache = set()
    
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
        if current_size >= settings.MAX_QUEUE_SIZE:
            logger.warning(f"Queue is full ({current_size}/{settings.MAX_QUEUE_SIZE})")
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
                self._duplicate_cache.add(sanitized_url.lower())
                
                logger.info(f"Added to queue: {sanitized_url} from {submitter_username}")
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
    
    def mark_as_playing(self, queue_entry_id: int) -> Tuple[bool, str]:
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
                
                entry.status = QueueEntryStatus.PLAYING
                session.commit()
                logger.info(f"Marked as playing: {queue_entry_id}")
                return True, f"Now playing: {entry.url}"
        except Exception as e:
            logger.error(f"Error marking as playing: {e}")
            return False, "Server error"
    
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
                entry.played_at = datetime.utcnow()
                
                # Update statistics
                stat = session.query(BotStatistic).first()
                if stat:
                    stat.total_links_played += 1
                
                session.commit()
                logger.info(f"Marked as completed: {queue_entry_id}")
                return True, "Entry marked as completed"
        except Exception as e:
            logger.error(f"Error marking as completed: {e}")
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
                entry.removed_at = datetime.utcnow()
                entry.notes = reason or entry.notes
                
                # Update statistics
                stat = session.query(BotStatistic).first()
                if stat:
                    stat.total_links_rejected += 1
                
                session.commit()
                logger.info(f"Removed from queue: {queue_entry_id}")
                return True, "Entry removed"
        except Exception as e:
            logger.error(f"Error removing from queue: {e}")
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
                        QueueEntry.id == entry_id
                    ).first()
                    
                    if entry:
                        entry.position = position
                
                session.commit()
                logger.info(f"Queue reordered: {len(order)} entries")
                return True, "Queue reordered successfully"
        except Exception as e:
            logger.error(f"Error reordering queue: {e}")
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
