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
from quetie.utils.diagnostics import record_diagnostic
from quetie.queue.manager import queue_manager
from quetie.runtime import runtime_state

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
    runtime_state.set_bot_status(enabled=bool(settings.TWITCH_OAUTH_TOKEN), connected=False, error=None)
    
    Database.close()
    logger.info("Shutdown complete")


def bootstrap_application() -> None:
    """Initialize shared app dependencies and restore persistent runtime state."""
    Database.initialize()
    SecurityManager.init_default_admin()
    filter_engine.refresh_filters()
    runtime_state.mark_startup_completed()
    record_diagnostic("app", "bootstrap_completed", mode="shared")


def start_bot_runtime() -> bool:
    """Start the Twitch bot background runtime when credentials are available."""
    global irc_client

    if not settings.TWITCH_OAUTH_TOKEN:
        logger.warning("TWITCH_OAUTH_TOKEN not configured; bot runtime disabled")
        runtime_state.set_bot_status(enabled=False, connected=False, error="missing_twitch_oauth_token")
        record_diagnostic("bot", "disabled", level="WARNING", reason="missing_twitch_oauth_token")
        return False

    irc_client = TwitchIRCClient(
        username=settings.TWITCH_BOT_USERNAME,
        oauth_token=settings.TWITCH_OAUTH_TOKEN,
        target_channel=settings.TWITCH_TARGET_CHANNEL
    )
    create_command_handlers(irc_client)

    started = irc_client.start()
    if started:
        logger.info(f"Bot connected to #{settings.TWITCH_TARGET_CHANNEL}")
        runtime_state.set_bot_status(enabled=True, connected=True, error=None)
        record_diagnostic("bot", "started", channel=settings.TWITCH_TARGET_CHANNEL)
        return True

    logger.error("Bot failed to start; continuing without chat runtime")
    runtime_state.set_bot_status(enabled=True, connected=False, error="failed_to_start")
    record_diagnostic("bot", "start_failed", level="ERROR", channel=settings.TWITCH_TARGET_CHANNEL)
    return False


def start_bot():
    """Start Twitch IRC bot only"""
    logger.info("Starting Twitch IRC Bot...")
    bootstrap_application()
    queue_manager.restore_runtime_state()
    if not start_bot_runtime():
        raise RuntimeError("Bot-only mode requested but Twitch bot could not start")
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
    bootstrap_application()

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
    bootstrap_application()
    start_bot_runtime()

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
    if args.mode == "bot" and not settings.TWITCH_OAUTH_TOKEN:
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
        runtime_state.mark_startup_error(str(e))
        record_diagnostic("app", "fatal_error", level="ERROR", error=str(e))
        shutdown()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
