"""
menu.py - Main menu callback handlers & Submit/Doubt conversation flows

Place this file at: bot/handlers/menu.py

Handles all inline-keyboard callbacks from the main menu:
  • Resources, Tasks, Meetings, Progress, Certificate → read-only data
  • Submit Work → conversation flow to collect submission text
  • Ask Doubt  → conversation flow to collect doubt text
"""

from telegram import Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from bot import sheets
from bot.keyboards import main_menu_keyboard, back_to_menu_keyboard

# Conversation states for Submit Work / Ask Doubt
AWAITING_SUBMISSION = 0
AWAITING_DOUBT = 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_verified(context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Check if the user has completed Gmail verification."""
    return context.user_data.get("verified", False)


async def _require_verification(update: Update) -> None:
    """Send a 'please verify first' message."""
    query = update.callback_query
    if query:
        await query.answer()
        await query.edit_message_text(
            "🔒 You need to verify your Gmail first.\n"
            "Send /start to begin verification."
        )


# ---------------------------------------------------------------------------
# Read-only menu callbacks
# ---------------------------------------------------------------------------

async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Route all menu_* callback queries to the right data column."""
    query = update.callback_query
    await query.answer()

    if not _is_verified(context):
        await _require_verification(update)
        return

    gmail = context.user_data["gmail"]
    name = context.user_data.get("name", "Intern")
    data = query.data

    # ---------- Resource Link ----------
    if data == "menu_resources":
        value = sheets.get_intern_data(gmail, "Resource Link")
        if value.startswith("📭"):
            text = f"📚 <b>Resources</b> for <b>{name}</b>:\n\n📭 No resources assigned yet. Check back soon!"
        else:
            text = f"📚 <b>Resources</b> for <b>{name}</b>:\n\n{value}"
        await query.edit_message_text(
            text,
            parse_mode="HTML",
            reply_markup=back_to_menu_keyboard(),
        )
        return

    # ---------- Doubts ----------
    if data == "menu_doubt":
        value = sheets.get_intern_data(gmail, "Doubts")
        if value.startswith("📭"):
            text = (
                f"❓ <b>Ask a Doubt</b>\n\n"
                "Please type your question or doubt below.\n\n"
                "Type /cancel to go back."
            )
            await query.edit_message_text(text, parse_mode="HTML")
            context.user_data["awaiting"] = "doubt"
        else:
            text = f"❓ <b>Your Doubts</b> for <b>{name}</b>:\n\n{value}"
            await query.edit_message_text(
                text,
                parse_mode="HTML",
                reply_markup=back_to_menu_keyboard(),
            )
        return

    # ---------- Meetings ----------
    if data == "menu_meetings":
        value = sheets.get_intern_data(gmail, "Meetings")
        if value.startswith("📭"):
            text = f"📅 <b>Meetings</b> for <b>{name}</b>:\n\n📭 No meetings scheduled yet. You will be notified soon!"
        else:
            text = f"📅 <b>Meetings</b> for <b>{name}</b>:\n\n{value}"
        await query.edit_message_text(
            text,
            parse_mode="HTML",
            reply_markup=back_to_menu_keyboard(),
        )
        return

    # ---------- Progress ----------
    if data == "menu_progress":
        value = sheets.get_intern_data(gmail, "Progress")
        if value.startswith("📭") or not value.strip():
            text = f"📊 <b>Progress</b> for <b>{name}</b>:\n\n⚪ 0% — No progress recorded yet. Complete your tasks to see progress!"
        else:
            text = f"📊 <b>Progress</b> for <b>{name}</b>:\n\n🚀 {value}"
        await query.edit_message_text(
            text,
            parse_mode="HTML",
            reply_markup=back_to_menu_keyboard(),
        )
        return


    # Handle menu_tasks specifically
    if data == "menu_tasks":
        task_val = sheets.get_intern_data(gmail, "Task")
        if "No Task data available yet" in task_val or not task_val.strip() or task_val.startswith("📭"):
            await query.edit_message_text(
                "📋 *Assigned Task*\n\n"
                "📭 No tasks assigned to you yet. Keep learning! 🚀",
                parse_mode="Markdown",
                reply_markup=back_to_menu_keyboard(),
            )
            return

        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        task_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📤 Submit Task", callback_data="menu_submit_task")],
            [InlineKeyboardButton("📊 Task Status", callback_data="menu_task_status")],
            [InlineKeyboardButton("🔙 Back to Menu", callback_data="back_menu")]
        ])

        await query.edit_message_text(
            f"📋 *Assigned Task*\n\n"
            f"{task_val}\n\n"
            f"━━━━━━━━━━━━━━━\n\n"
            f"Submission Type:\n"
            f"GitHub Link / Drive Link / Live Website Link\n\n"
            f"Click the button below when your task is completed.",
            parse_mode="Markdown",
            reply_markup=task_kb,
        )
        return

    # Handle menu_submit_task specifically
    if data == "menu_submit_task":
        sub_data = sheets.get_task_submission_data(gmail)
        if not sub_data:
            await query.edit_message_text(
                "❌ *No record found.*",
                parse_mode="Markdown",
                reply_markup=back_to_menu_keyboard(),
            )
            return

        task_val = sub_data.get("task", "").strip()
        if not task_val:
            await query.edit_message_text(
                "📋 *Submit Task*\n\n"
                "📭 No tasks assigned to you yet. You can only submit once a task is assigned.",
                parse_mode="Markdown",
                reply_markup=back_to_menu_keyboard(),
            )
            return

        existing_link = sub_data.get("submission_link", "").strip()
        if existing_link:
            # Duplicate warning
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup
            confirm_kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Yes", callback_data="menu_confirm_replace_sub")],
                [InlineKeyboardButton("❌ No", callback_data="back_menu")]
            ])
            await query.edit_message_text(
                f"You have already submitted this task.\n\n"
                f"*Current Submission:*\n{existing_link}\n\n"
                f"Do you want to replace it?",
                parse_mode="Markdown",
                reply_markup=confirm_kb,
            )
        else:
            # Direct prompt
            await query.edit_message_text(
                "🔗 *Please send your task submission link.*\n\n"
                "Accepted examples:\n"
                "• https://github.com/username/project\n"
                "• https://drive.google.com/...\n"
                "• https://yourproject.vercel.app\n\n"
                "Type /cancel to go back.",
                parse_mode="Markdown",
            )
            context.user_data["awaiting"] = "task_submission"
        return

    # Handle menu_confirm_replace_sub specifically
    if data == "menu_confirm_replace_sub":
        await query.edit_message_text(
            "🔗 *Please send your task submission link.*\n\n"
            "Accepted examples:\n"
            "• https://github.com/username/project\n"
            "• https://drive.google.com/...\n"
            "• https://yourproject.vercel.app\n\n"
            "Type /cancel to go back.",
            parse_mode="Markdown",
        )
        context.user_data["awaiting"] = "task_submission"
        return

    # Handle menu_task_status specifically
    if data == "menu_task_status":
        sub_data = sheets.get_task_submission_data(gmail)
        if not sub_data:
            await query.edit_message_text(
                "❌ *No record found.*",
                parse_mode="Markdown",
                reply_markup=back_to_menu_keyboard(),
            )
            return

        task = sub_data.get("task", "") or "No task assigned yet."
        link = sub_data.get("submission_link", "") or "No submission link yet."
        status_val = sub_data.get("status", "").strip().upper()
        remarks = sub_data.get("remarks", "") or "No remarks yet."

        status_display = "🟡 Submitted"
        if status_val == "APPROVED":
            status_display = "🟢 APPROVED"
        elif status_val == "REJECTED":
            status_display = "🔴 REJECTED"
        elif not status_val or status_val == "PENDING":
            status_display = "⚪ Pending"
        else:
            status_display = f"⚪ {status_val.capitalize()}"

        await query.edit_message_text(
            f"📊 *Task Status*\n\n"
            f"*Task Title:*\n{task}\n\n"
            f"*Submission:*\n{link}\n\n"
            f"*Status:*\n{status_display}\n\n"
            f"*Mentor Remarks:*\n{remarks}",
            parse_mode="Markdown",
            reply_markup=back_to_menu_keyboard(),
        )
        return

    # Handle Certificate option specifically
    if data == "menu_certificate":
        eligible, reason = sheets.is_eligible_for_certificate(gmail)
        if not eligible:
            await query.edit_message_text(
                f"❌ *Certificate Request Denied*\n\n"
                f"You are not eligible for certificate processing yet.\n\n"
                f"*Reason:* {reason}\n\n"
                f"Please ensure all your tasks are completed and APPROVED.",
                parse_mode="Markdown",
                reply_markup=back_to_menu_keyboard(),
            )
            return

        cert_data = sheets.get_certificate_data(gmail)
        if not cert_data:
            await query.edit_message_text(
                "❌ *No certificate profile found.*",
                parse_mode="Markdown",
                reply_markup=back_to_menu_keyboard(),
            )
            return

        name_cert = cert_data.get("name_certificate", "").strip()
        college = cert_data.get("college_name", "").strip()
        project = cert_data.get("project_title", "").strip()
        comp_date = cert_data.get("completion_date", "").strip()
        serial = cert_data.get("serial_number", "").strip()
        status = cert_data.get("status", "").strip().upper()
        url = cert_data.get("url", "").strip()

        if not name_cert:
            # Column N is empty, start guided certificate profile form
            await query.edit_message_text(
                "🎓 *Certificate Profile Form*\n\n"
                "Please fill in your details to request a certificate.\n\n"
                "👤 *Name for Certificate*\n"
                "Please type your full name as you want it to appear on your certificate.\n\n"
                "Type /cancel to abort.",
                parse_mode="Markdown",
            )
            context.user_data["awaiting"] = "cert_name"
            return

        if status == "GENERATED" and url:
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup
            download_kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("⬇️ Download Certificate", url=url)],
                [InlineKeyboardButton("🔙 Back to Menu", callback_data="back_menu")]
            ])
            await query.edit_message_text(
                f"🎉 *Congratulations! Your certificate is ready!* 🎓\n\n"
                f"👤 *Name:* {name_cert}\n"
                f"🏫 *College:* {college}\n"
                f"📝 *Project:* {project or 'N/A'}\n"
                f"📅 *Completion Date:* {comp_date or 'N/A'}\n"
                f"🔢 *Serial Number:* {serial}\n\n"
                f"You can download your certificate using the button below.",
                parse_mode="Markdown",
                reply_markup=download_kb,
            )
        else:
            # Treat as pending (or if they filled but status isn't GENERATED/PENDING)
            await query.edit_message_text(
                f"⏳ *Certificate Status*\n\n"
                f"Your certificate is under review and will be issued shortly.\n\n"
                f"👤 *Name:* {name_cert}\n"
                f"🏫 *College:* {college}\n"
                f"📝 *Project:* {project or 'N/A'}\n"
                f"📅 *Completion Date:* {comp_date or 'N/A'}\n"
                f"🔢 *Serial:* {serial}\n",
                parse_mode="Markdown",
                reply_markup=back_to_menu_keyboard(),
            )
        return

    # Submit Work & Ask Doubt are handled by their own ConversationHandlers
    # (see below). This callback just prompts the user to type their text.
    if data == "menu_submit":
        await query.edit_message_text(
            "📤 *Submit Work*\n\n"
            "Please type your submission details below.\n"
            "Include any links or descriptions of completed work.\n\n"
            "Type /cancel to go back.",
            parse_mode="Markdown",
        )
        # Store a flag so the text handler knows what to do
        context.user_data["awaiting"] = "submission"
        return





async def back_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the 'Back to Menu' button."""
    query = update.callback_query
    await query.answer()

    if not _is_verified(context):
        await _require_verification(update)
        return

    name = context.user_data.get("name", "Intern")
    await query.edit_message_text(
        f"📋 *Main Menu* — Welcome back, *{name}*!\n\n"
        "Choose an option below:",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(),
    )


# ---------------------------------------------------------------------------
# Free-text handler for Submit Work / Ask Doubt
# ---------------------------------------------------------------------------

async def handle_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Catch free-text messages from verified users.
    If they were prompted for a submission or doubt, process it.
    """
    if not _is_verified(context):
        await update.message.reply_text(
            "🔒 Please verify your Gmail first with /start."
        )
        return

    awaiting = context.user_data.pop("awaiting", None)
    gmail = context.user_data["gmail"]
    text = update.message.text.strip()

    if awaiting == "cert_name":
        context.user_data["cert_name_input"] = text
        await update.message.reply_text(
            "🏫 *College Name*\n\nPlease type your college or university name below:\n\nType /cancel to abort.",
            parse_mode="Markdown",
        )
        context.user_data["awaiting"] = "cert_college"
        return

    if awaiting == "cert_college":
        name_cert = context.user_data.pop("cert_name_input", "").strip()
        college = text

        # Save certificate details and auto-generate serial number
        serial = sheets.save_certificate_details(gmail, name_cert, college)

        if serial:
            await update.message.reply_text(
                f"✅ *Certificate request submitted successfully!* 🎓\n\n"
                f"👤 *Name on Certificate:* {name_cert}\n"
                f"🏫 *College:* {college}\n"
                f"🔢 *Serial Number:* {serial}\n\n"
                f"Your certificate is under review and will be issued shortly.",
                parse_mode="Markdown",
                reply_markup=main_menu_keyboard(),
            )
        else:
            await update.message.reply_text(
                "⚠️ Failed to save your certificate details. Please try again later.",
                reply_markup=main_menu_keyboard(),
            )
        return

    if awaiting == "task_submission":
        # Link Validation: verify it starts with http:// or https://
        if not (text.lower().startswith("http://") or text.lower().startswith("https://")):
            await update.message.reply_text(
                "❌ *Invalid link.*\n\n"
                "Please submit a valid GitHub, Google Drive, or Website URL.\n\n"
                "Send the link again or type /cancel to go back.",
                parse_mode="Markdown",
            )
            context.user_data["awaiting"] = "task_submission"
            return

        success = sheets.save_task_submission(gmail, text)
        if success:
            await update.message.reply_text(
                f"✅ *Task Submitted Successfully*\n\n"
                f"Your submission has been sent for mentor review.\n\n"
                f"*Submission Link:*\n{text}\n\n"
                f"*Current Status:*\n🟡 Submitted",
                parse_mode="Markdown",
                reply_markup=main_menu_keyboard(),
            )
        else:
            await update.message.reply_text(
                "⚠️ Failed to save task submission. Please try again later.",
                reply_markup=main_menu_keyboard(),
            )
        return

    if awaiting == "submission":
        success = sheets.submit_work(gmail, text)
        if success:
            await update.message.reply_text(
                "✅ *Submission recorded!* Keep up the great work! 💪",
                parse_mode="Markdown",
                reply_markup=main_menu_keyboard(),
            )
        else:
            await update.message.reply_text(
                "⚠️ Failed to record submission. Please try again later.",
                reply_markup=main_menu_keyboard(),
            )
        return

    if awaiting == "doubt":
        success = sheets.submit_doubt(gmail, text)
        if success:
            await update.message.reply_text(
                "✅ *Your doubt has been shared to your mentor.* You will get an answer soon. 📩",
                parse_mode="Markdown",
                reply_markup=main_menu_keyboard(),
            )
            # Notify admins about the doubt
            from bot.config import ADMIN_IDS
            for admin_id in ADMIN_IDS:
                try:
                    await context.bot.send_message(
                        chat_id=admin_id,
                        text=f"❓ *New Doubt from {gmail}*\n\n{text}\n\n*Reply using:*\n`/replydoubt {gmail} Your answer here`",
                        parse_mode="Markdown",
                    )
                except Exception:
                    pass
        else:
            await update.message.reply_text(
                "⚠️ Failed to record doubt. Please try again later.",
                reply_markup=main_menu_keyboard(),
            )
        return

    # If user sends random text outside any flow, show the menu
    await update.message.reply_text(
        "💡 Use the menu to navigate. Send /menu to see options.",
        reply_markup=main_menu_keyboard(),
    )


# ---------------------------------------------------------------------------
# /menu command (re-show the menu anytime)
# ---------------------------------------------------------------------------

async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the main menu. Available after verification."""
    if not _is_verified(context):
        await update.message.reply_text(
            "🔒 Please verify your Gmail first with /start."
        )
        return

    name = context.user_data.get("name", "Intern")
    await update.message.reply_text(
        f"📋 *Main Menu* — *{name}*\n\nChoose an option below:",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(),
    )


# ---------------------------------------------------------------------------
# Handler registration
# ---------------------------------------------------------------------------

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Cancel any active text-input flow and go back to main menu."""
    if not _is_verified(context):
        await update.message.reply_text(
            "🔒 Please verify your Gmail first with /start."
        )
        return

    context.user_data.pop("awaiting", None)
    context.user_data.pop("cert_name_input", None)
    await update.message.reply_text(
        "❌ Action cancelled.",
        reply_markup=main_menu_keyboard()
    )


def get_menu_handlers() -> list:
    """Return all handlers for the menu system."""
    return [
        CommandHandler("menu", menu_command),
        CommandHandler("cancel", cancel_command),
        CallbackQueryHandler(menu_callback, pattern=r"^menu_"),
        CallbackQueryHandler(back_to_menu, pattern=r"^back_menu$"),
        # Free-text handler — must be added AFTER ConversationHandlers
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_input),
    ]
