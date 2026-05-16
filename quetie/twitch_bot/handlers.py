"""
Command handlers for Twitch bot
Processes user commands and routes them to appropriate handlers
"""

from quetie.queue.manager import queue_manager
from quetie.utils.logger import setup_logger

logger = setup_logger(__name__)


class CommandHandlers:
    """Handlers for Twitch chat commands"""
    
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
        Handle !add command - add link to queue
        Format: !add <url> [notes]
        
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
        
        # Extract URL (first "word" which could be the entire first argument if it's a URL)
        parts = args.split(" ", 1)
        url = parts[0].strip()
        notes = parts[1].strip() if len(parts) > 1 else None
        
        # Add to queue
        success, message, entry_id = queue_manager.add_to_queue(
            url=url,
            submitter_username=username,
            notes=notes
        )
        
        if success:
            logger.info(f"Queue entry added: {entry_id} from {username}")
            self.irc_client.send_message(f"@{username} {message}")
        else:
            logger.warning(f"Queue rejection: {message} from {username}")
            self.irc_client.send_message(f"@{username} {message}")
    
    def handle_help(self, username: str, args: str) -> None:
        """
        Handle !queuehelp command - display help information
        
        Args:
            username: User who issued command
            args: Command arguments (unused)
        """
        help_messages = [
            "Queue Commands:",
            "!add <url> - Submit a link to the queue",
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
