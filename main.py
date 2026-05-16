"""
Quetie_mbg - Main entry point
Orchestrates Twitch IRC bot and web dashboard
"""

import sys
import argparse
import signal
import uvicorn
from quetie.config.settings import settings
from quetie.db.database import Database
from quetie.twitch_bot.client import TwitchIRCClient
from quetie.twitch_bot.handlers import create_command_handlers
from quetie.web.auth import SecurityManager
from quetie.web.app import create_app
from quetie.filtering.filters import filter_engine
from quetie.utils.logger import setup_logger

logger = setup_logger(__name__)

# Global references for graceful shutdown
irc_client = None
app = None


def signal_handler(sig, frame):
    """Handle shutdown signals gracefully"""
    logger.info(f"Received signal {sig}, shutting down...")
    shutdown()
    sys.exit(0)


def shutdown():
    """Graceful shutdown"""
    if irc_client and irc_client.running:
        logger.info("Stopping IRC client...")
        irc_client.stop()
    
    Database.close()
    logger.info("Shutdown complete")


def start_bot():
    """Start Twitch IRC bot only"""
    logger.info("Starting Twitch IRC Bot...")
    
    # Initialize database
    Database.initialize()
    
    # Initialize default admin
    SecurityManager.init_default_admin()
    
    # Refresh filter cache
    filter_engine.refresh_filters()
    
    # Create IRC client
    global irc_client
    irc_client = TwitchIRCClient(
        username=settings.TWITCH_BOT_USERNAME,
        oauth_token=settings.TWITCH_OAUTH_TOKEN,
        target_channel=settings.TWITCH_TARGET_CHANNEL
    )
    
    # Register command handlers
    create_command_handlers(irc_client)
    
    # Start IRC client
    irc_client.start()
    
    logger.info(f"Bot connected to #{settings.TWITCH_TARGET_CHANNEL}")
    logger.info("Bot is running (Press Ctrl+C to stop)")
    
    # Keep running
    try:
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Bot shutdown requested")
        shutdown()


def start_web():
    """Start web dashboard only"""
    logger.info("Starting Web Dashboard...")
    
    # Initialize database
    Database.initialize()
    
    # Initialize default admin
    SecurityManager.init_default_admin()
    
    # Refresh filter cache
    filter_engine.refresh_filters()
    
    # Create app
    global app
    app = create_app()
    
    logger.info(f"Starting web server on {settings.WEB_HOST}:{settings.WEB_PORT}")
    
    # Run uvicorn
    uvicorn.run(
        app,
        host=settings.WEB_HOST,
        port=settings.WEB_PORT,
        workers=1,
        log_level=settings.LOG_LEVEL.lower()
    )


def start_all():
    """Start both bot and web dashboard"""
    logger.info("Starting Quetie_mbg (Bot + Web Dashboard)...")
    
    # Initialize database
    Database.initialize()
    
    # Initialize default admin
    SecurityManager.init_default_admin()
    
    # Refresh filter cache
    filter_engine.refresh_filters()
    
    # Create and start IRC client in background thread
    global irc_client
    irc_client = TwitchIRCClient(
        username=settings.TWITCH_BOT_USERNAME,
        oauth_token=settings.TWITCH_OAUTH_TOKEN,
        target_channel=settings.TWITCH_TARGET_CHANNEL
    )
    
    # Register command handlers
    create_command_handlers(irc_client)
    
    # Start IRC client (runs in background thread)
    irc_client.start()
    logger.info(f"Bot connected to #{settings.TWITCH_TARGET_CHANNEL}")
    
    # Create and start web app
    global app
    app = create_app()
    
    logger.info(f"Starting web server on {settings.WEB_HOST}:{settings.WEB_PORT}")
    
    # Run uvicorn (blocking)
    uvicorn.run(
        app,
        host=settings.WEB_HOST,
        port=settings.WEB_PORT,
        workers=1,
        log_level=settings.LOG_LEVEL.lower()
    )


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Quetie_mbg - Twitch Queue Management Bot"
    )
    
    parser.add_argument(
        "--mode",
        choices=["bot", "web", "all"],
        default="all",
        help="Mode to run: bot only, web only, or both (default: all)"
    )
    
    parser.add_argument(
        "--config",
        help="Path to .env configuration file"
    )
    
    parser.add_argument(
        "--init-db",
        action="store_true",
        help="Initialize database and exit"
    )
    
    parser.add_argument(
        "--version",
        action="store_true",
        help="Show version and exit"
    )
    
    args = parser.parse_args()
    
    # Show version
    if args.version:
        print("Quetie_mbg v1.0.0")
        return 0
    
    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Initialize database if requested
    if args.init_db:
        logger.info("Initializing database...")
        Database.initialize()
        logger.info("Database initialized successfully")
        return 0
    
    # Validate Twitch configuration
    if (args.mode in ["bot", "all"]) and not settings.TWITCH_OAUTH_TOKEN:
        logger.error("TWITCH_OAUTH_TOKEN is required to run bot mode")
        return 1
    
    # Start appropriate mode
    try:
        if args.mode == "bot":
            start_bot()
        elif args.mode == "web":
            start_web()
        else:  # all
            start_all()
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        shutdown()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
