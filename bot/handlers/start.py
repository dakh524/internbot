"""
start.py - /start command & Gmail verification flow

Place this file at: bot/handlers/start.py

Flow:
1. User sends /start
2. Bot checks if the Telegram ID is already linked in Google Sheet
3. If already linked → skip verification, load data, show menu
4. If not linked → ask for Gmail → look up in Sheet → verify
"""

from telegram import Update
from telegram.ext import (
    CommandHandler,
    ConversationHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from bot import sheets
from bot.keyboards import main_menu_keyboard

# Conversation states
AWAITING_GMAIL = 0


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle /start — check if already verified, otherwise ask for Gmail."""
    telegram_id = update.effective_user.id

    # Check if this Telegram ID is already linked in the sheet
    try:
        intern = sheets.find_intern_by_telegram_id(telegram_id)
    except Exception:
        intern = None

    if intern is not None:
        # Already verified — restore session data and show menu directly
        # Sheet header is lowercase 'gmail'; fall back to 'Gmail' for safety
        gmail = str(intern.get("gmail") or intern.get("Gmail") or "").strip()
        name = str(intern.get("Name", "Intern")).strip()
        context.user_data["gmail"] = gmail
        context.user_data["name"] = name
        context.user_data["verified"] = True

        await update.message.reply_text(
            f"👋 *Welcome back, {name}!* 🎉\n\n"
            "You're already verified. Use the menu below to navigate:",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard(),
        )
        return ConversationHandler.END

    # Not yet linked — ask for Gmail
    await update.message.reply_text(
        "👋 *Welcome to the Internship Management Bot!*\n\n"
        "Please enter your *Gmail address* to verify your identity:",
        parse_mode="Markdown",
    )
    return AWAITING_GMAIL


async def receive_gmail(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Validate the Gmail the user entered."""
    gmail = update.message.text.strip()

    # Basic format check
    if "@" not in gmail or not gmail.endswith("@gmail.com"):
        await update.message.reply_text(
            "⚠️ That doesn't look like a valid Gmail address.\n"
            "Please enter a valid *@gmail.com* address:",
            parse_mode="Markdown",
        )
        return AWAITING_GMAIL

    # Look up in Google Sheet
    try:
        intern = sheets.find_intern_by_gmail(gmail)
    except Exception as exc:
        await update.message.reply_text(
            f"⚠️ Error connecting to the database: `{exc}`\n"
            "Please try again later with /start.",
            parse_mode="Markdown",
        )
        return ConversationHandler.END

    if intern is None:
        # Log unregistered visitor details to a separate sheet tab
        try:
            user = update.effective_user
            sheets.log_unregistered_visitor(
                gmail=gmail,
                telegram_id=user.id,
                telegram_username=user.username,
                full_name=user.full_name,
            )
        except Exception:
            pass  # Don't block the user if logging fails

        await update.message.reply_text(
            "❌ *Gmail not found in our records.*\n\n"
            "An internship opportunity is waiting for you! Join our internship program by registering here:\n"
            "👉 https://intern-registration.vercel.app/\n\n"
            "Once you have registered and received an offer, type /start to try again.",
            parse_mode="Markdown",
        )
        return ConversationHandler.END

    # Check Offer Status
    offer_status = str(intern.get("Offer Status", intern.get("Offer Letter Status", ""))).strip().upper()
    if offer_status != "ISSUED":
        await update.message.reply_text(
            f"🚫 Your offer status is *{offer_status or 'UNKNOWN'}*.\n"
            "Access is only granted when your offer status is *ISSUED*.\n\n"
            "Please contact the admin if you believe this is an error.",
            parse_mode="Markdown",
        )
        return ConversationHandler.END

    # Success — save Telegram ID and grant access
    telegram_id = update.effective_user.id
    sheets.save_telegram_id(gmail, telegram_id)

    # Persist gmail in user_data so other handlers can use it
    context.user_data["gmail"] = gmail
    context.user_data["name"] = intern.get("Name", "Intern")
    context.user_data["verified"] = True

    domain = intern.get("Domain", "N/A")
    offer_status_display = intern.get("Offer Status", intern.get("Offer Letter Status", "N/A"))
    
    welcome_text = (
        "🎉 *Welcome to DAKH EDU SOLUTION Internship Program!*\n\n"
        f"Dear {context.user_data['name']},\n\n"
        "Happy to connect with you! 👋\n\n"
        "I am InternBot, your internship assistant. Your administrator has assigned me to support and guide you throughout your internship journey.\n\n"
        "✅ *Verification Successful*\n\n"
        f"📌 *Name:* {context.user_data['name']}\n"
        f"💻 *Domain:* {domain}\n"
        f"📄 *Offer Status:* {offer_status_display}\n\n"
        f"As a {domain} Intern, you will gain hands-on experience in both frontend and backend technologies, work on practical projects, access learning resources, and build industry-relevant skills.\n\n"
        "Through this platform, you can:\n\n"
        "📚 Access learning resources\n"
        "📝 View assigned tasks\n"
        "📤 Submit your work\n"
        "📅 Join internship meetings\n"
        "📊 Track your progress\n"
        "❓ Ask doubts anytime\n"
        "🎓 Check certificate status\n\n"
        "Remember, every successful developer started as a beginner. Focus on learning consistently, completing your tasks, and improving a little every day.\n\n"
        "💬 *Message from DAKH EDU SOLUTION CEO:*\n\n"
        "\"Skills are the real currency of the future. Invest your time in learning today, and opportunities will follow tomorrow.\"\n\n"
        "We are excited to have you as part of our internship community and look forward to seeing your growth and achievements.\n\n"
        "🚀 Wishing you a successful internship journey!\n\n"
        "Regards,\n"
        "InternBot\n"
        "DAKH EDU SOLUTION"
    )

    await update.message.reply_text(
        welcome_text,
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(),
    )
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Allow the user to cancel the verification flow."""
    await update.message.reply_text(
        "❌ Verification cancelled. Type /start to begin again."
    )
    return ConversationHandler.END


def get_start_handler() -> ConversationHandler:
    """Build and return the ConversationHandler for /start."""
    return ConversationHandler(
        entry_points=[CommandHandler("start", start_command)],
        states={
            AWAITING_GMAIL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_gmail),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,  # Allow /start to restart the flow at any time
    )
