"""
config.py - Environment configuration loader

Place this file at: bot/config.py

Loads all environment variables from .env file and provides
them as module-level constants for the rest of the application.
"""

import os
from dotenv import load_dotenv

# Load .env file from project root
load_dotenv()

# Telegram Bot Token (from @BotFather)
TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")

# Google Sheet ID (extracted from the spreadsheet URL)
GOOGLE_SHEET_ID: str = os.getenv(
    "GOOGLE_SHEET_ID",
    "1VYUyXQPoLR8_CCZtBmtBvPt2TTofFqtKpM1bjVkriG4",
)

# Path to the Google Service Account credentials JSON
GOOGLE_CREDENTIALS_PATH: str = os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json")

# Raw Google credentials JSON string (useful for cloud environments)
GOOGLE_CREDENTIALS_JSON: str = os.getenv("GOOGLE_CREDENTIALS_JSON", "")

# Timezone for scheduled tasks (defaults to Asia/Kolkata)
TIMEZONE: str = os.getenv("TIMEZONE", "Asia/Kolkata")

# Admin Telegram user IDs who can use /broadcast, /interns, /stats
ADMIN_IDS: list[int] = [
    int(uid.strip())
    for uid in os.getenv("ADMIN_IDS", "").split(",")
    if uid.strip().isdigit()
]


def validate() -> None:
    """Raise early if critical config is missing."""
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set in .env")
    if not GOOGLE_SHEET_ID:
        raise RuntimeError("GOOGLE_SHEET_ID is not set in .env")
    
    # Check if either credentials JSON string or credentials file is available
    if not GOOGLE_CREDENTIALS_JSON and not os.path.exists(GOOGLE_CREDENTIALS_PATH):
        raise FileNotFoundError(
            f"Google credentials file not found at: {GOOGLE_CREDENTIALS_PATH} and GOOGLE_CREDENTIALS_JSON is not set in the environment."
        )

