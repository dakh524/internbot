"""
keyboards.py - Reusable Inline Keyboard layouts

Place this file at: bot/keyboards.py

All keyboard definitions live here so handlers stay clean.
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu_keyboard() -> InlineKeyboardMarkup:
    """Return the primary intern menu keyboard."""
    buttons = [
        [
            InlineKeyboardButton("📚 Resources", callback_data="menu_resources"),
            InlineKeyboardButton("📝 Tasks", callback_data="menu_tasks"),
        ],
        [
            InlineKeyboardButton("📤 Submit Task", callback_data="menu_submit_task"),
            InlineKeyboardButton("❓ Ask Doubt", callback_data="menu_doubt"),
        ],
        [
            InlineKeyboardButton("📅 Meetings", callback_data="menu_meetings"),
            InlineKeyboardButton("📊 Progress", callback_data="menu_progress"),
        ],
        [
            InlineKeyboardButton("📋 Task Status", callback_data="menu_task_status"),
            InlineKeyboardButton("🎓 Certificate", callback_data="menu_certificate"),
        ],
    ]
    return InlineKeyboardMarkup(buttons)


def back_to_menu_keyboard() -> InlineKeyboardMarkup:
    """Single 'Back to Menu' button for returning after viewing info."""
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("🔙 Back to Menu", callback_data="back_menu")]]
    )
