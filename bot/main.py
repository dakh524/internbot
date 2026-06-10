"""
main.py - Application entry point

Place this file at: bot/main.py

Run with:  python -m bot.main
"""

import asyncio
import logging
import os
import traceback
import html
import json

import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, ContextTypes
from telegram.request import HTTPXRequest

from bot.config import TELEGRAM_BOT_TOKEN, validate, ADMIN_IDS
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


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log the error and send a telegram message to notify the developer/admin."""
    # Log the error with traceback
    logger.error("Exception while handling an update:", exc_info=context.error)

    try:
        # traceback.format_exception returns the list of strings wrapper
        tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
        tb_string = "".join(tb_list)

        # Build the message
        update_str = update.to_dict() if isinstance(update, Update) else str(update)
        message = (
            f"⚠️ <b>An exception was raised while handling an update</b>\n\n"
            f"<b>Update:</b>\n<code>{html.escape(json.dumps(update_str, indent=2, ensure_ascii=False))[:1000]}</code>\n\n"
            f"<b>Traceback:</b>\n<code>{html.escape(tb_string)[:3000]}</code>"
        )

        # Send message to all admins
        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=message,
                    parse_mode=ParseMode.HTML
                )
            except Exception as e:
                logger.error(f"Failed to send error notification to admin {admin_id}: {e}")
    except Exception as e:
        logger.error(f"Failed to execute error handler: {e}")


# ---------------------------------------------------------------------------
# Health-check HTTP server (required for Render port-scan to pass)
# ---------------------------------------------------------------------------

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'OK')

    def do_HEAD(self):
        # UptimeRobot and similar monitors use HEAD requests.
        # HEAD is identical to GET but must not include a response body.
        self.send_response(200)
        self.end_headers()

    def log_message(self, format, *args):
        pass  # Silence default request logging


def run_health_server_thread():
    port = int(os.environ.get('PORT', 8080))
    server = HTTPServer(('0.0.0.0', port), HealthHandler)
    logger.info(f"🌐 Health server started on port {port}")
    server.serve_forever()


# ---------------------------------------------------------------------------
# Bot setup
# ---------------------------------------------------------------------------

async def run_bot() -> None:
    """Build, configure, and run the Telegram bot using the async lifecycle API."""
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
        .get_updates_request(
            HTTPXRequest(
                read_timeout=30,
                write_timeout=30,
                connect_timeout=30,
                pool_timeout=30,
            )
        )
        .build()
    )

    # Register global error handler
    app.add_error_handler(error_handler)

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

    # Use the lower-level async lifecycle so we can share the event loop
    # with the health-check server (run_polling() would own the loop itself).
    logger.info("🚀 InternBot is starting...")
    async with app:
        await app.start()
        await app.updater.start_polling(drop_pending_updates=True)
        # Block here until a stop signal is received (SIGINT / SIGTERM).
        await asyncio.Event().wait()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Start the health-check thread, then run the Telegram bot."""
    threading.Thread(target=run_health_server_thread, daemon=True).start()
    asyncio.run(run_bot())


if __name__ == "__main__":
    main()
