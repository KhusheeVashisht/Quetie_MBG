"""
Command handlers for Twitch bot
Processes user commands and routes them to appropriate handlers
"""

import re
import shlex
import urllib.parse
import urllib.request
from typing import Optional

from quetie.queue.manager import queue_manager
from quetie.utils.logger import setup_logger

logger = setup_logger(__name__)


class CommandHandlers:
    """Handlers for Twitch chat commands"""

    URL_PATTERN = re.compile(r'https?://[^\s<>"\']+', re.IGNORECASE)
    VIDEO_ID_PATTERNS = [
        re.compile(r'"videoId":"([A-Za-z0-9_-]{11})"'),
        re.compile(r'href="/watch\?v=([A-Za-z0-9_-]{11})"'),
        re.compile(r'watch\?v=([A-Za-z0-9_-]{11})'),
    ]
    
    def __init__(self, irc_client):
        """
        Initialize command handlers
        
        Args:
            irc_client: TwitchIRCClient instance
        """
        self.irc_client = irc_client
        self._register_handlers()
    
    def _register_handlers(self) -> None:
        """Register all command handlers with IRC client"""
        self.irc_client.register_handler("!queue", self.handle_queue)
        self.irc_client.register_handler("!add", self.handle_add)
        self.irc_client.register_handler("!link", self.handle_add)  # Alias
        self.irc_client.register_handler("!submit", self.handle_add)  # Alias
        self.irc_client.register_handler("!queuehelp", self.handle_help)
        self.irc_client.register_handler("!queuesize", self.handle_queuesize)
        logger.info("Command handlers registered")

    def _resolve_youtube_query(self, query: str) -> Optional[str]:
        """Resolve a free-text query to a likely YouTube video URL."""
        normalized = (query or "").strip()
        if not normalized:
            return None

        search_url = "https://www.youtube.com/results?search_query=" + urllib.parse.quote_plus(normalized)
        request = urllib.request.Request(
            search_url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            },
        )

        try:
            with urllib.request.urlopen(request, timeout=6) as response:
                body = response.read().decode("utf-8", errors="ignore")
        except Exception as e:
            logger.warning(f"Failed to resolve YouTube query '{normalized}': {e}")
            body = ""

        youtube_url = self._extract_youtube_url(body)
        if youtube_url:
            return youtube_url

        return self._resolve_youtube_query_via_duckduckgo(normalized)

    def _resolve_youtube_query_via_duckduckgo(self, query: str) -> Optional[str]:
        """Fallback to DuckDuckGo HTML search and extract the first YouTube result."""
        search_url = "https://duckduckgo.com/html/?q=" + urllib.parse.quote_plus(f"site:youtube.com {query}")
        request = urllib.request.Request(
            search_url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            },
        )

        try:
            with urllib.request.urlopen(request, timeout=6) as response:
                body = response.read().decode("utf-8", errors="ignore")
        except Exception as e:
            logger.warning(f"DuckDuckGo fallback failed for '{query}': {e}")
            return None

        for match in re.finditer(r'uddg=([^&"\']+)', body):
            candidate = urllib.parse.unquote(match.group(1))
            candidate = candidate.rstrip(".,)\"'")
            if "youtube.com/watch" in candidate or "youtu.be/" in candidate:
                return candidate

        return None

    def _extract_youtube_url(self, body: str) -> Optional[str]:
        """Extract the first likely video URL from a YouTube results page."""
        for pattern in self.VIDEO_ID_PATTERNS:
            match = pattern.search(body or "")
            if match:
                video_id = match.group(1)
                return f"https://www.youtube.com/watch?v={video_id}"

        return None
    
    def handle_queue(self, username: str, args: str) -> None:
        """
        Handle !queue command - display queue size and next link
        
        Args:
            username: User who issued command
            args: Command arguments
        """
        try:
            queue, total = queue_manager.get_queue(limit=1)
            
            if not queue:
                self.irc_client.send_message("Queue is empty!")
                return
            
            next_link = queue[0]
            submitter = next_link.get("submitter_username", "Unknown")
            
            response = f"Next in queue: {next_link['url']} (from @{submitter})"
            self.irc_client.send_message(response)
            logger.info(f"Sent queue info to {username}")
        
        except Exception as e:
            logger.error(f"Error in !queue command: {e}")
            self.irc_client.send_message("Error retrieving queue information")
    
    def handle_add(self, username: str, args: str) -> None:
        """
        Handle !add command - add one or more links to queue
        Format: !add <url> [url2 ...] [notes]
        
        Args:
            username: User who issued command
            args: URL to add (rest of message after !add)
        """
        if not args:
            self.irc_client.send_message(
                f"Usage: !add <url> - Submit a link to the queue. "
                f"Type !queuehelp for more info."
            )
            return

        urls = self.URL_PATTERN.findall(args)
        if not urls:
            has_separators = bool(re.search(r"[\r\n;,|]", args))
            normalized = re.sub(r"[\r\n;,|]+", " ", args).strip()
            try:
                parts = shlex.split(normalized)
            except ValueError:
                parts = [segment for segment in normalized.split() if segment]

            if not parts:
                self.irc_client.send_message(
                    f"@{username} No valid URLs or searchable song names found. Use !add <url> or !add <song1> <song2>."
                )
                return

            if len(parts) > 1 and not has_separators and len(parts) != 2:
                parts = [normalized]

            results = []
            for part in parts:
                resolved = self._resolve_youtube_query(part)
                if not resolved:
                    results.append((part, None, False, f"No match for: {part}", None))
                    continue
                success, message, entry_id = queue_manager.add_to_queue(
                    url=resolved,
                    submitter_username=username,
                    notes=f"Query: {part}"
                )
                results.append((part, resolved, success, message, entry_id))

            added = sum(1 for _, _, success, _, _ in results if success)
            failed = len(results) - added
            if failed == 0:
                if len(results) == 1:
                    _, resolved_url, _, message, _ = results[0]
                    self.irc_client.send_message(f"@{username} {message} (matched: {resolved_url})")
                    return

                positions = []
                for _, _, _, message, _ in results:
                    m = re.search(r"position\s+(\d+)", message, re.IGNORECASE)
                    positions.append(m.group(1) if m else "?")
                self.irc_client.send_message(f"@{username} Queued {added} items at positions: {', '.join(positions)}")
            else:
                failed_item = next((part for part, _, success, _, _ in results if not success), None)
                first_fail = next((m for _, _, success, m, _ in results if not success), "Some items failed")
                if failed_item:
                    first_fail = f"{failed_item}: {first_fail}"
                self.irc_client.send_message(
                    f"@{username} Queued {added}/{len(results)} items; {first_fail} - not added"
                )
            return

        if len(urls) == 1:
            notes = None
            remaining = args.replace(urls[0], "", 1).strip()
            if remaining:
                notes = remaining

            success, message, entry_id = queue_manager.add_to_queue(
                url=urls[0],
                submitter_username=username,
                notes=notes
            )

            if success:
                logger.info(f"Queue entry added: {entry_id} from {username}")
            else:
                logger.warning(f"Queue rejection: {message} from {username}")

            self.irc_client.send_message(f"@{username} {message}")
            return

        results = []
        for url in urls:
            success, message, entry_id = queue_manager.add_to_queue(
                url=url,
                submitter_username=username,
            )
            results.append((url, success, message, entry_id))

        added = sum(1 for _, success, _, _ in results if success)
        failed = len(results) - added
        logger.info(f"Processed {len(results)} queued links from {username}: {added} added, {failed} failed")

        added_positions = []
        for index, (_, success, message, _) in enumerate(results, start=1):
            if not success:
                continue
            position_match = re.search(r"position\s+(\d+)", message, re.IGNORECASE)
            if position_match:
                added_positions.append(position_match.group(1))
            else:
                added_positions.append(str(index))

        failed_messages = [message for _, success, message, _ in results if not success]

        if failed == 0:
            positions_preview = ", ".join(added_positions[:10])
            suffix = "" if len(added_positions) <= 10 else ", ..."
            self.irc_client.send_message(
                f"@{username} Queued {added} links at positions: {positions_preview}{suffix}"
            )
            return

        failed_item = next((url for url, success, _, _ in results if not success), None)
        failure_hint = failed_messages[0] if failed_messages else "Some links could not be queued"
        if failed_item:
            failure_hint = f"{failed_item}: {failure_hint}"
        self.irc_client.send_message(
            f"@{username} Queued {added}/{len(results)} links (positions: {', '.join(added_positions[:10])}); {failure_hint} - not added"
        )
    
    def handle_help(self, username: str, args: str) -> None:
        """
        Handle !queuehelp command - display help information
        
        Args:
            username: User who issued command
            args: Command arguments (unused)
        """
        help_messages = [
            "Queue Commands:",
            "!add <url> [url2 ...] - Submit one or more links to the queue",
            "!add <song or video name> - Auto-search YouTube and queue the top result",
            "!queue - Show next link in queue",
            "!queuesize - Show current queue size",
            "Only valid links are accepted. Discord/social links rejected.",
        ]
        
        for msg in help_messages:
            self.irc_client.send_message(msg)
        
        logger.info(f"Sent help info to {username}")
    
    def handle_queuesize(self, username: str, args: str) -> None:
        """
        Handle !queuesize command - display queue size
        
        Args:
            username: User who issued command
            args: Command arguments (unused)
        """
        try:
            _, total = queue_manager.get_queue(limit=1)
            self.irc_client.send_message(
                f"Queue size: {total} links waiting"
            )
            logger.info(f"Sent queue size to {username}")
        except Exception as e:
            logger.error(f"Error in !queuesize command: {e}")
            self.irc_client.send_message("Error retrieving queue size")


def create_command_handlers(irc_client):
    """Factory function to create and initialize command handlers"""
    return CommandHandlers(irc_client)
