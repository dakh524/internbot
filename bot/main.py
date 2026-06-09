"""
main.py - Application entry point

Place this file at: bot/main.py

Run with:  python -m bot.main
"""

import logging

from telegram.ext import ApplicationBuilder
from telegram.request import HTTPXRequest

from bot.config import TELEGRAM_BOT_TOKEN, validate
from bot.handlers.start import get_start_handler
from bot.handlers.menu import get_menu_handlers
from bot.handlers.admin import get_admin_handlers

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def main() -> None:
    """Initialize and start the bot."""
    # Validate configuration before doing anything else
    validate()
    logger.info("✅ Configuration validated successfully.")

    # Build application with generous timeouts for slower connections
    request = HTTPXRequest(
        read_timeout=30,
        write_timeout=30,
        connect_timeout=30,
        pool_timeout=30,
    )
    app = (
        ApplicationBuilder()
        .token(TELEGRAM_BOT_TOKEN)
        .request(request)
        .get_updates_request(HTTPXRequest(read_timeout=30, write_timeout=30, connect_timeout=30, pool_timeout=30))
        .build()
    )

    # Register handlers (order matters!)
    # 1. ConversationHandler for /start (must come first)
    app.add_handler(get_start_handler())

    # 2. Admin command handlers
    for handler in get_admin_handlers():
        app.add_handler(handler)

    # 3. Menu callback + free-text handlers
    for handler in get_menu_handlers():
        app.add_handler(handler)

    # Setup background jobs
    from bot.jobs import setup_daily_jobs
    if app.job_queue:
        setup_daily_jobs(app.job_queue)
    else:
        logger.warning("JobQueue is not enabled! Scheduled jobs will not run.")

    # Start polling
    logger.info("🚀 InternBot is starting...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
