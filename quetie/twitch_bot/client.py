"""
Twitch IRC Bot Client for Quetie_mbg
Handles IRC connection, message parsing, and command routing
"""

import socket
import threading
import time
from typing import Callable, Dict, Optional
from quetie.utils.logger import setup_logger
from quetie.utils.diagnostics import record_diagnostic

logger = setup_logger(__name__)


class TwitchIRCMessage:
    """Represents a parsed IRC message"""
    
    def __init__(self, raw_message: str):
        """
        Parse IRC message
        
        Args:
            raw_message: Raw IRC message string
        """
        self.raw = raw_message
        self.tags = {}
        self.prefix = None
        self.command = None
        self.params = []
        self.user = None
        self.channel = None
        self.message = None
        
        self._parse()
    
    def _parse(self) -> None:
        """Parse IRC message components"""
        message = self.raw.strip()
        
        # Parse tags
        if message.startswith("@"):
            tags_part, message = message.split(" ", 1)
            self.tags = self._parse_tags(tags_part[1:])
        
        # Parse prefix
        if message.startswith(":"):
            prefix_part, message = message.split(" ", 1)
            self.prefix = prefix_part[1:]
            
            # Extract user from prefix (format: user!user@host)
            if "!" in self.prefix:
                self.user = self.prefix.split("!")[0]
        
        # Parse command and params
        parts = message.split(" ")
        self.command = parts[0]
        
        # Parse parameters
        for i in range(1, len(parts)):
            if parts[i].startswith(":"):
                # Rest is message content
                self.message = " ".join(parts[i:])[1:]
                break
            else:
                self.params.append(parts[i])
        
        # Extract channel from params
        if self.params and self.params[0].startswith("#"):
            self.channel = self.params[0]
    
    def _parse_tags(self, tags_str: str) -> Dict[str, str]:
        """Parse IRC tags"""
        tags = {}
        for tag in tags_str.split(";"):
            if "=" in tag:
                key, value = tag.split("=", 1)
                tags[key] = value
        return tags
    
    def __repr__(self) -> str:
        return f"<TwitchIRCMessage cmd={self.command} user={self.user} channel={self.channel}>"


class TwitchIRCClient:
    """Twitch IRC Bot Client with automatic reconnection"""
    
    def __init__(
        self,
        username: str,
        oauth_token: str,
        target_channel: str
    ):
        """
        Initialize Twitch IRC client
        
        Args:
            username: Bot username (e.g., 'miss_brain_glitch_bot')
            oauth_token: OAuth token with 'chat:read:messages' and 'chat:edit'
            target_channel: Channel to connect to (e.g., 'miss_brain_glitch')
        """
        self.username = username
        self.oauth_token = oauth_token
        self.target_channel = target_channel.lower()
        
        self.socket = None
        self.connected = False
        self.running = False
        
        # Command handlers
        self._command_handlers: Dict[str, Callable] = {}
        
        # Connection parameters
        self.host = "irc.chat.twitch.tv"
        self.port = 6667
        self.reconnect_delay = 5  # Start with 5 seconds
        self.reconnect_max_delay = 300  # Max 5 minutes
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 10
        
        # Threading
        self._thread = None
        self._stop_event = threading.Event()
    
    def register_handler(self, command: str, handler: Callable) -> None:
        """
        Register a command handler
        
        Args:
            command: Command name (e.g., '!queue')
            handler: Callback function that takes (user, message) as args
        """
        self._command_handlers[command.lower()] = handler
        logger.debug(f"Registered handler for command: {command}")
    
    def connect(self) -> bool:
        """
        Connect to Twitch IRC
        
        Returns:
            True if successfully connected, False otherwise
        """
        try:
            logger.info(f"Connecting to {self.host}:{self.port}...")
            if self.socket:
                try:
                    self.socket.close()
                except Exception:
                    pass
            self.socket = socket.socket()
            self.socket.settimeout(30)
            self.socket.connect((self.host, self.port))
            
            # Send login credentials
            self._send_raw(f"PASS {self.oauth_token}")
            self._send_raw(f"NICK {self.username}")
            self._send_raw(f"USER {self.username} 8 * :{self.username}")
            
            # Request capability
            self._send_raw("CAP REQ :twitch.tv/tags twitch.tv/commands twitch.tv/membership")
            
            # Join channel
            self._send_raw(f"JOIN #{self.target_channel}")
            
            self.connected = True
            self.reconnect_attempts = 0
            self.reconnect_delay = 5
            
            logger.info(f"Connected to Twitch IRC - Channel: #{self.target_channel}")
            record_diagnostic("bot", "connected", channel=self.target_channel)
            return True
        
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            self.connected = False
            record_diagnostic("bot", "connect_failed", level="ERROR", error=str(e))
            return False
    
    def _send_raw(self, message: str) -> None:
        """Send raw IRC message"""
        if self.socket:
            try:
                self.socket.send((message + "\r\n").encode())
                logger.debug(f"Sent: {message}")
            except Exception as e:
                logger.error(f"Error sending message: {e}")
                self.connected = False
    
    def send_message(self, message: str) -> None:
        """
        Send a message to the channel
        
        Args:
            message: Message to send
        """
        if not message or len(message) > 500:
            logger.warning(f"Invalid message length: {len(message)}")
            return
        
        self._send_raw(f"PRIVMSG #{self.target_channel} :{message}")
    
    def _handle_message(self, irc_msg: TwitchIRCMessage) -> None:
        """Handle incoming IRC message"""
        if irc_msg.command == "PING":
            self._send_raw(f"PONG :{irc_msg.message}")
            return
        
        # Handle PRIVMSG (chat messages)
        if irc_msg.command == "PRIVMSG" and irc_msg.message:
            self._handle_privmsg(irc_msg)
    
    def _handle_privmsg(self, irc_msg: TwitchIRCMessage) -> None:
        """Handle private message (chat)"""
        if not irc_msg.user or not irc_msg.message:
            return
        
        message = irc_msg.message.strip()
        
        # Check if message is a command
        if message.startswith("!"):
            parts = message.split(" ", 1)
            command = parts[0].lower()
            args = parts[1] if len(parts) > 1 else ""
            
            # Find handler
            if command in self._command_handlers:
                try:
                    handler = self._command_handlers[command]
                    handler(irc_msg.user, args)
                except Exception as e:
                    logger.error(f"Error handling command {command}: {e}")
    
    def _read_messages(self) -> None:
        """Read messages from IRC socket"""
        try:
            while self.running and self.connected:
                try:
                    data = self.socket.recv(4096).decode(errors="ignore")
                    if not data:
                        logger.warning("No data received, disconnecting...")
                        self.connected = False
                        record_diagnostic("bot", "socket_closed")
                        break
                    
                    for line in data.split("\r\n"):
                        if line:
                            msg = TwitchIRCMessage(line)
                            self._handle_message(msg)
                except socket.timeout:
                    continue
                except Exception as e:
                    logger.error(f"Error reading message: {e}")
                    self.connected = False
                    record_diagnostic("bot", "read_failed", level="ERROR", error=str(e))
                    break
        
        except Exception as e:
            logger.error(f"Error in message read loop: {e}")
        finally:
            self.connected = False
    
    def _reconnect(self) -> None:
        """Handle reconnection with exponential backoff"""
        while self.running and not self.connected:
            try:
                self.reconnect_attempts += 1
                
                if self.reconnect_attempts > self.max_reconnect_attempts:
                    logger.error("Max reconnection attempts exceeded")
                    record_diagnostic("bot", "reconnect_exhausted", level="ERROR")
                    self.running = False
                    break
                
                logger.info(f"Reconnection attempt {self.reconnect_attempts} in {self.reconnect_delay}s...")
                if self._stop_event.wait(self.reconnect_delay):
                    return
                
                if self.connect():
                    break
                
                # Exponential backoff
                self.reconnect_delay = min(
                    self.reconnect_delay * 2,
                    self.reconnect_max_delay
                )
            
            except Exception as e:
                logger.error(f"Error during reconnection: {e}")
    
    def start(self) -> bool:
        """Start the IRC client in a background thread"""
        if self.running:
            logger.warning("Client already running")
            return True
        
        self.running = True
        self._stop_event.clear()
        
        # Initial connection
        if not self.connect():
            self.running = False
            return False
        
        # Start message reading thread
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info("IRC client started")
        return True
    
    def _run(self) -> None:
        """Main run loop with reconnection handling"""
        while self.running:
            try:
                if not self.connected:
                    self._reconnect()
                
                if self.connected:
                    self._read_messages()
            
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                self.connected = False
        
        logger.info("IRC client run loop stopped")
    
    def stop(self) -> None:
        """Stop the IRC client"""
        logger.info("Stopping IRC client...")
        self.running = False
        self._stop_event.set()
        
        if self.socket:
            try:
                self.socket.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            try:
                self.socket.close()
            except Exception as e:
                logger.error(f"Error closing socket: {e}")
        
        self.connected = False
        
        if self._thread:
            self._thread.join(timeout=5)
        
        logger.info("IRC client stopped")
    
    def is_connected(self) -> bool:
        """Check if currently connected"""
        return self.connected and self.running
