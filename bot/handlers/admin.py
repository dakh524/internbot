"""
admin.py - Admin-only commands

Place this file at: bot/handlers/admin.py

Commands:
    /broadcast <message>        — Send a message to all linked interns
    /interns                    — List all interns
    /stats                      — Show aggregate stats
    /addresource <gmail> <text> — Add a resource for an intern
    /addtask <gmail> <text>     — Add a task for an intern
    /addmeeting <gmail> <text>  — Add a meeting for an intern
    /setprogress <gmail> <text> — Set progress for an intern
    /addresourceall <text>      — Add a resource for ALL interns
    /addtaskall <text>          — Add a task for ALL interns
    /replydoubt <gmail> <text>  — Reply to an intern's doubt
    /scheduleresource <gmail> <YYYY-MM-DD HH:MM> <text> — Schedule a resource
    /scheduletask <gmail> <YYYY-MM-DD HH:MM> <text> — Schedule a task

Only users whose Telegram ID is in ADMIN_IDS (from .env) can use these.
"""

import datetime
from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

from bot import sheets
from bot.config import ADMIN_IDS
from bot.jobs import deliver_scheduled_message_job


def _is_admin(user_id: int) -> bool:
    """Check if the Telegram user ID is in the admin list."""
    return user_id in ADMIN_IDS


async def _admin_guard(update: Update) -> bool:
    """Return True if user is NOT admin (and send denial). False if admin."""
    if not _is_admin(update.effective_user.id):
        await update.message.reply_text("🚫 You are not authorized to use this command.")
        return True
    return False


# ---------------------------------------------------------------------------
# /broadcast <message>
# ---------------------------------------------------------------------------

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Send a message (text, photo, video, document) to all interns.
    Usage: /broadcast Your message here
           Or reply to a message with /broadcast
           Or send media with /broadcast in the caption
    """
    if await _admin_guard(update):
        return

    reply_to = update.message.reply_to_message
    message_text = " ".join(context.args) if context.args else ""

    if not reply_to and not message_text and not update.message.photo and not update.message.document and not update.message.video:
        await update.message.reply_text(
            "⚠️ *Usage:* `/broadcast Your message here`\n"
            "Or reply to any message with `/broadcast`\n"
            "Or send an image/document/video with `/broadcast [caption]`",
            parse_mode="Markdown",
        )
        return

    records = sheets.get_all_records()

    sent_count = 0
    fail_count = 0

    # Prepare caption prefix
    caption_prefix = "📢 *Broadcast from Admin:*\n\n"
    final_caption = f"{caption_prefix}{message_text}" if message_text else caption_prefix.strip()

    for record in records:
        tg_id = str(record.get("Telegram ID", "")).strip()
        if not tg_id or not tg_id.isdigit():
            continue
            
        chat_id = int(tg_id)
        try:
            if reply_to:
                await context.bot.copy_message(
                    chat_id=chat_id,
                    from_chat_id=update.message.chat_id,
                    message_id=reply_to.message_id
                )
            elif update.message.photo:
                await context.bot.send_photo(
                    chat_id=chat_id,
                    photo=update.message.photo[-1].file_id,
                    caption=final_caption,
                    parse_mode="Markdown",
                )
            elif update.message.video:
                await context.bot.send_video(
                    chat_id=chat_id,
                    video=update.message.video.file_id,
                    caption=final_caption,
                    parse_mode="Markdown",
                )
            elif update.message.document:
                await context.bot.send_document(
                    chat_id=chat_id,
                    document=update.message.document.file_id,
                    caption=final_caption,
                    parse_mode="Markdown",
                )
            else:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=final_caption,
                    parse_mode="Markdown",
                )
            sent_count += 1
        except Exception:
            fail_count += 1

    await update.message.reply_text(
        f"✅ Broadcast complete!\n"
        f"• Sent: {sent_count}\n"
        f"• Failed: {fail_count}",
    )


# ---------------------------------------------------------------------------
# /interns
# ---------------------------------------------------------------------------

async def interns_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List all interns with their key details."""
    if await _admin_guard(update):
        return

    interns = sheets.get_all_interns_summary()
    if not interns:
        await update.message.reply_text("📭 No intern records found.")
        return

    # Build a readable list (Telegram has a 4096-char message limit)
    lines = ["👥 *Intern List:*\n"]
    for i, intern in enumerate(interns, 1):
        tg_status = "✅" if str(intern["Telegram ID"]).strip() else "❌"
        lines.append(
            f"*{i}.* {intern['Name']}\n"
            f"    📧 {intern['Gmail']}\n"
            f"    📋 Status: {intern['Offer Status']}\n"
            f"    📱 Telegram: {tg_status}\n"
            f"    🏷 Domain: {intern.get('Domain', 'N/A')}\n"
        )

    full_text = "\n".join(lines)

    # Split into chunks if too long
    if len(full_text) <= 4000:
        await update.message.reply_text(full_text, parse_mode="Markdown")
    else:
        # Send in chunks
        chunk = ""
        for line in lines:
            if len(chunk) + len(line) > 3900:
                await update.message.reply_text(chunk, parse_mode="Markdown")
                chunk = ""
            chunk += line + "\n"
        if chunk.strip():
            await update.message.reply_text(chunk, parse_mode="Markdown")


# ---------------------------------------------------------------------------
# /stats
# ---------------------------------------------------------------------------

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show aggregate internship stats."""
    if await _admin_guard(update):
        return

    stats = sheets.get_stats()
    await update.message.reply_text(
        "📊 *Internship Statistics:*\n\n"
        f"👥 Total Interns: *{stats['total_interns']}*\n"
        f"✅ Offers Issued: *{stats['offers_issued']}*\n"
        f"⏳ Pending: *{stats['pending']}*\n"
        f"📱 Telegram Linked: *{stats['telegram_linked']}*",
        parse_mode="Markdown",
    )


# ---------------------------------------------------------------------------
# /addresource <gmail> <resource text>
# ---------------------------------------------------------------------------

async def add_resource_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Add a resource for a specific intern.
    Usage: /addresource intern@gmail.com Resource link or description
    """
    if await _admin_guard(update):
        return

    if len(context.args) < 2:
        await update.message.reply_text(
            "⚠️ *Usage:* `/addresource intern@gmail.com Resource text here`",
            parse_mode="Markdown",
        )
        return

    gmail = context.args[0]
    resource_text = " ".join(context.args[1:])

    try:
        success = sheets.set_intern_resource(gmail, resource_text)
    except Exception as exc:
        await update.message.reply_text(f"⚠️ Error: `{exc}`", parse_mode="Markdown")
        return

    if success:
        await update.message.reply_text(
            f"✅ Resource added for *{gmail}*:\n\n📚 {resource_text}",
            parse_mode="Markdown",
        )
    else:
        await update.message.reply_text(
            f"❌ Gmail *{gmail}* not found in the sheet.",
            parse_mode="Markdown",
        )


# ---------------------------------------------------------------------------
# /addtask <gmail> <task text>
# ---------------------------------------------------------------------------

async def add_task_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Add a task for a specific intern.
    Usage: /addtask intern@gmail.com Task description
    """
    if await _admin_guard(update):
        return

    if len(context.args) < 2:
        await update.message.reply_text(
            "⚠️ *Usage:* `/addtask intern@gmail.com Task description here`",
            parse_mode="Markdown",
        )
        return

    gmail = context.args[0]
    task_text = " ".join(context.args[1:])

    try:
        success = sheets.set_intern_task(gmail, task_text)
    except Exception as exc:
        await update.message.reply_text(f"⚠️ Error: `{exc}`", parse_mode="Markdown")
        return

    if success:
        await update.message.reply_text(
            f"✅ Task added for *{gmail}*:\n\n📝 {task_text}",
            parse_mode="Markdown",
        )
    else:
        await update.message.reply_text(
            f"❌ Gmail *{gmail}* not found in the sheet.",
            parse_mode="Markdown",
        )


# ---------------------------------------------------------------------------
# Scheduled Commands
# ---------------------------------------------------------------------------

async def schedule_resource_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Schedule a resource to be delivered at a specific time.
    Usage: /scheduleresource intern@gmail.com 2026-06-10 14:30 Resource text
    """
    if await _admin_guard(update):
        return

    if len(context.args) < 4:
        await update.message.reply_text(
            "⚠️ *Usage:* `/scheduleresource intern@gmail.com YYYY-MM-DD HH:MM Resource text`\n"
            "Example: `/scheduleresource user@gmail.com 2026-06-10 14:30 Check out this video`",
            parse_mode="Markdown",
        )
        return

    gmail = context.args[0]
    date_str = context.args[1]
    time_str = context.args[2]
    resource_text = " ".join(context.args[3:])

    # Parse datetime
    try:
        dt = datetime.datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    except ValueError:
        await update.message.reply_text("❌ Invalid date/time format. Use `YYYY-MM-DD HH:MM`.")
        return

    if dt < datetime.datetime.now():
        await update.message.reply_text("❌ Scheduled time must be in the future.")
        return

    tg_id = sheets.get_telegram_id_by_gmail(gmail)
    if not tg_id:
        await update.message.reply_text(f"❌ Gmail *{gmail}* is not found or hasn't linked Telegram.", parse_mode="Markdown")
        return

    # Schedule the job
    context.job_queue.run_once(
        deliver_scheduled_message_job,
        when=dt,
        data={
            "gmail": gmail,
            "tg_id": tg_id,
            "type": "Resource",
            "text": resource_text
        },
        name=f"sched_res_{gmail}_{dt.timestamp()}"
    )

    await update.message.reply_text(
        f"✅ Resource scheduled for *{gmail}* on *{date_str} at {time_str}*.",
        parse_mode="Markdown",
    )


async def schedule_task_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Schedule a task to be delivered at a specific time.
    Usage: /scheduletask intern@gmail.com 2026-06-10 14:30 Task description
    """
    if await _admin_guard(update):
        return

    if len(context.args) < 4:
        await update.message.reply_text(
            "⚠️ *Usage:* `/scheduletask intern@gmail.com YYYY-MM-DD HH:MM Task description`\n"
            "Example: `/scheduletask user@gmail.com 2026-06-10 14:30 Complete module 4`",
            parse_mode="Markdown",
        )
        return

    gmail = context.args[0]
    date_str = context.args[1]
    time_str = context.args[2]
    task_text = " ".join(context.args[3:])

    # Parse datetime
    try:
        dt = datetime.datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    except ValueError:
        await update.message.reply_text("❌ Invalid date/time format. Use `YYYY-MM-DD HH:MM`.")
        return

    if dt < datetime.datetime.now():
        await update.message.reply_text("❌ Scheduled time must be in the future.")
        return

    tg_id = sheets.get_telegram_id_by_gmail(gmail)
    if not tg_id:
        await update.message.reply_text(f"❌ Gmail *{gmail}* is not found or hasn't linked Telegram.", parse_mode="Markdown")
        return

    # Schedule the job
    context.job_queue.run_once(
        deliver_scheduled_message_job,
        when=dt,
        data={
            "gmail": gmail,
            "tg_id": tg_id,
            "type": "Task",
            "text": task_text
        },
        name=f"sched_task_{gmail}_{dt.timestamp()}"
    )

    await update.message.reply_text(
        f"✅ Task scheduled for *{gmail}* on *{date_str} at {time_str}*.",
        parse_mode="Markdown",
    )


# ---------------------------------------------------------------------------
# /addmeeting <gmail> <meeting text>
# ---------------------------------------------------------------------------

async def add_meeting_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Add a meeting for a specific intern.
    Usage: /addmeeting intern@gmail.com Meeting details
    """
    if await _admin_guard(update):
        return

    if len(context.args) < 2:
        await update.message.reply_text(
            "⚠️ *Usage:* `/addmeeting intern@gmail.com Meeting details here`",
            parse_mode="Markdown",
        )
        return

    gmail = context.args[0]
    meeting_text = " ".join(context.args[1:])

    try:
        success = sheets.set_intern_meeting(gmail, meeting_text)
    except Exception as exc:
        await update.message.reply_text(f"⚠️ Error: `{exc}`", parse_mode="Markdown")
        return

    if success:
        await update.message.reply_text(
            f"✅ Meeting added for *{gmail}*:\n\n📅 {meeting_text}",
            parse_mode="Markdown",
        )
    else:
        await update.message.reply_text(
            f"❌ Gmail *{gmail}* not found in the sheet.",
            parse_mode="Markdown",
        )


# ---------------------------------------------------------------------------
# /setprogress <gmail> <progress text>
# ---------------------------------------------------------------------------

async def set_progress_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Set progress for a specific intern (overwrites previous value).
    Usage: /setprogress intern@gmail.com 75% - Completed module 3
    """
    if await _admin_guard(update):
        return

    if len(context.args) < 2:
        await update.message.reply_text(
            "⚠️ *Usage:* `/setprogress intern@gmail.com Progress text here`",
            parse_mode="Markdown",
        )
        return

    gmail = context.args[0]
    progress_text = " ".join(context.args[1:])

    try:
        success = sheets.set_intern_progress(gmail, progress_text)
    except Exception as exc:
        await update.message.reply_text(f"⚠️ Error: `{exc}`", parse_mode="Markdown")
        return

    if success:
        await update.message.reply_text(
            f"✅ Progress updated for *{gmail}*:\n\n📊 {progress_text}",
            parse_mode="Markdown",
        )
    else:
        await update.message.reply_text(
            f"❌ Gmail *{gmail}* not found in the sheet.",
            parse_mode="Markdown",
        )


# ---------------------------------------------------------------------------
# /addresourceall <resource text>  — bulk add to ALL interns
# ---------------------------------------------------------------------------

async def add_resource_all_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Add a resource for ALL interns at once.
    Usage: /addresourceall Resource link or description
    """
    if await _admin_guard(update):
        return

    if not context.args:
        await update.message.reply_text(
            "⚠️ *Usage:* `/addresourceall Resource text here`",
            parse_mode="Markdown",
        )
        return

    resource_text = " ".join(context.args)
    gmails = sheets.get_all_gmails()

    success_count = 0
    fail_count = 0

    for gmail in gmails:
        try:
            if sheets.set_intern_resource(gmail, resource_text):
                success_count += 1
            else:
                fail_count += 1
        except Exception:
            fail_count += 1

    await update.message.reply_text(
        f"✅ Resource added for *{success_count}* intern(s)!\n"
        f"❌ Failed: {fail_count}\n\n"
        f"📚 {resource_text}",
        parse_mode="Markdown",
    )


# ---------------------------------------------------------------------------
# /addtaskall <task text>  — bulk add to ALL interns
# ---------------------------------------------------------------------------

async def add_task_all_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Add a task for ALL interns at once.
    Usage: /addtaskall Task description
    """
    if await _admin_guard(update):
        return

    if not context.args:
        await update.message.reply_text(
            "⚠️ *Usage:* `/addtaskall Task description here`",
            parse_mode="Markdown",
        )
        return

    task_text = " ".join(context.args)
    gmails = sheets.get_all_gmails()

    success_count = 0
    fail_count = 0

    for gmail in gmails:
        try:
            if sheets.set_intern_task(gmail, task_text):
                success_count += 1
            else:
                fail_count += 1
        except Exception:
            fail_count += 1

    await update.message.reply_text(
        f"✅ Task added for *{success_count}* intern(s)!\n"
        f"❌ Failed: {fail_count}\n\n"
        f"📝 {task_text}",
        parse_mode="Markdown",
    )


# ---------------------------------------------------------------------------
# /replydoubt <gmail> <answer text>
# ---------------------------------------------------------------------------

async def reply_doubt_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Reply to an intern's doubt. The answer is sent directly to them via Telegram.
    Usage: /replydoubt intern@gmail.com The answer is X.
    """
    if await _admin_guard(update):
        return

    if len(context.args) < 2:
        await update.message.reply_text(
            "⚠️ *Usage:* `/replydoubt intern@gmail.com Your answer here`",
            parse_mode="Markdown",
        )
        return

    gmail = context.args[0]
    answer_text = " ".join(context.args[1:])

    # Find the intern's Telegram ID
    tg_id = sheets.get_telegram_id_by_gmail(gmail)
    if not tg_id:
        await update.message.reply_text(
            f"❌ Cannot send message. Gmail *{gmail}* is not found or hasn't linked Telegram.",
            parse_mode="Markdown",
        )
        return

    # Send the answer to the intern
    try:
        await context.bot.send_message(
            chat_id=tg_id,
            text=f"👨‍🏫 *Mentor Reply to your Doubt:*\n\n{answer_text}",
            parse_mode="Markdown",
        )
        await update.message.reply_text(f"✅ Reply sent to {gmail}.")
    except Exception as exc:
        await update.message.reply_text(f"⚠️ Failed to send message: `{exc}`", parse_mode="Markdown")


# ---------------------------------------------------------------------------
# /unregistered — view all unregistered visitors
# ---------------------------------------------------------------------------

async def unregistered_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List all unregistered visitors who tried the bot."""
    if await _admin_guard(update):
        return

    try:
        visitors = sheets.get_unregistered_visitors()
    except Exception as exc:
        await update.message.reply_text(f"⚠️ Error: `{exc}`", parse_mode="Markdown")
        return

    if not visitors:
        await update.message.reply_text("📭 No unregistered visitors yet.")
        return

    lines = ["👤 *Unregistered Visitors:*\n"]
    for i, v in enumerate(visitors, 1):
        gmail = v.get("Gmail", "N/A")
        tg_user = v.get("Telegram Username", "N/A")
        name = v.get("Full Name", "N/A")
        date = v.get("Date", "N/A")
        time_str = v.get("Time", "")
        lines.append(f"{i}. {gmail} — {name} (@{tg_user}) on {date} {time_str}")

    # Telegram has a 4096 char limit; truncate if too long
    msg = "\n".join(lines)
    if len(msg) > 4000:
        msg = msg[:4000] + "\n\n_...truncated. Check the Google Sheet for the full list._"

    await update.message.reply_text(msg, parse_mode="Markdown")


# ---------------------------------------------------------------------------
# Task Submission Approvals
# ---------------------------------------------------------------------------

async def review_submissions_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List all student submissions whose status is SUBMITTED."""
    if await _admin_guard(update):
        return

    try:
        submitted = sheets.get_submitted_tasks()
    except Exception as exc:
        await update.message.reply_text(f"⚠️ Error: `{exc}`", parse_mode="Markdown")
        return

    if not submitted:
        await update.message.reply_text("📭 No submitted tasks waiting for review.")
        return

    lines = ["📝 *Submissions for Review:*\n"]
    for i, s in enumerate(submitted, 1):
        lines.append(
            f"*{i}.* {s['name']} ({s['gmail']})\n"
            f"    📋 *Task:* {s['task']}\n"
            f"    🔗 *Link:* {s['link']}\n"
            f"    📅 *Date:* {s['date']}\n"
        )

    msg = "\n".join(lines)
    if len(msg) > 4000:
        msg = msg[:4000] + "\n\n_...truncated._"
    await update.message.reply_text(msg, parse_mode="Markdown")


async def approve_task_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Approve an intern's task submission.
    Usage: /approvetask intern@gmail.com [remarks...]
    """
    if await _admin_guard(update):
        return

    if not context.args:
        await update.message.reply_text(
            "⚠️ *Usage:* `/approvetask intern@gmail.com [optional remarks...]`",
            parse_mode="Markdown",
        )
        return

    gmail = context.args[0]
    remarks = " ".join(context.args[1:]) if len(context.args) > 1 else "Good job!"

    try:
        success = sheets.update_task_status_in_sheet(gmail, "APPROVED", remarks)
        if not success:
            await update.message.reply_text(f"❌ Failed to find record for {gmail}.")
            return

        # Notify the student
        tg_id = sheets.get_telegram_id_by_gmail(gmail)
        if tg_id:
            try:
                await context.bot.send_message(
                    chat_id=tg_id,
                    text=(
                        "✅ *Task Approved*\n\n"
                        "Congratulations!\n\n"
                        "Your submission has been reviewed and approved.\n\n"
                        f"*Mentor Remarks:*\n{remarks}"
                    ),
                    parse_mode="Markdown",
                )
            except Exception:
                pass

        await update.message.reply_text(f"✅ Submission for {gmail} approved.")
    except Exception as exc:
        await update.message.reply_text(f"⚠️ Error: `{exc}`", parse_mode="Markdown")


async def reject_task_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Reject an intern's task submission with remarks.
    Usage: /rejecttask intern@gmail.com <remarks...>
    """
    if await _admin_guard(update):
        return

    if len(context.args) < 2:
        await update.message.reply_text(
            "⚠️ *Usage:* `/rejecttask intern@gmail.com <remarks...>`",
            parse_mode="Markdown",
        )
        return

    gmail = context.args[0]
    remarks = " ".join(context.args[1:])

    try:
        success = sheets.update_task_status_in_sheet(gmail, "REJECTED", remarks)
        if not success:
            await update.message.reply_text(f"❌ Failed to find record for {gmail}.")
            return

        # Notify the student
        tg_id = sheets.get_telegram_id_by_gmail(gmail)
        if tg_id:
            try:
                await context.bot.send_message(
                    chat_id=tg_id,
                    text=(
                        "❌ *Task Needs Improvement*\n\n"
                        f"*Mentor Remarks:*\n{remarks}\n\n"
                        "Please review and resubmit."
                    ),
                    parse_mode="Markdown",
                )
            except Exception:
                pass

        await update.message.reply_text(f"❌ Submission for {gmail} rejected (needs improvement).")
    except Exception as exc:
        await update.message.reply_text(f"⚠️ Error: `{exc}`", parse_mode="Markdown")


# ---------------------------------------------------------------------------
# /adminhelp — show all admin commands
# ---------------------------------------------------------------------------

async def admin_help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show all available admin commands."""
    if await _admin_guard(update):
        return

    await update.message.reply_text(
        "🛠 *Admin Commands:*\n\n"
        "*📢 Broadcast:*\n"
        "`/broadcast <message>` — Send to all linked interns\n\n"
        "*👥 View:*\n"
        "`/interns` — List all interns\n"
        "`/stats` — Show aggregate stats\n\n"
        "*📚 Per-Intern:*\n"
        "`/addresource <gmail> <text>` — Add resource\n"
        "`/addtask <gmail> <text>` — Add task\n"
        "`/addmeeting <gmail> <text>` — Add meeting\n"
        "`/setprogress <gmail> <text>` — Set progress\n\n"
        "*⏰ Scheduled:*\n"
        "`/scheduleresource <gmail> <YYYY-MM-DD HH:MM> <text>`\n"
        "`/scheduletask <gmail> <YYYY-MM-DD HH:MM> <text>`\n\n"
        "*📦 Bulk (All Interns):*\n"
        "`/addresourceall <text>` — Add resource for all\n"
        "`/addtaskall <text>` — Add task for all\n\n"
        "*💬 Mentorship:*\n"
        "`/replydoubt <gmail> <text>` — Answer doubt\n\n"
        "*👤 Leads:*\n"
        "`/unregistered` — View unregistered visitors\n\n"
        "*📥 Submissions:*\n"
        "`/reviewsubmissions` — View tasks to review\n"
        "`/approvetask <gmail> [remarks]` — Approve task\n"
        "`/rejecttask <gmail> <remarks>` — Reject task\n\n"
        "*ℹ️ Help:*\n"
        "`/adminhelp` — Show this message",
        parse_mode="Markdown",
    )


# ---------------------------------------------------------------------------
# Handler registration
# ---------------------------------------------------------------------------

def get_admin_handlers() -> list:
    """Return all admin command handlers."""
    return [
        CommandHandler("broadcast", broadcast_command),
        CommandHandler("interns", interns_command),
        CommandHandler("stats", stats_command),
        CommandHandler("addresource", add_resource_command),
        CommandHandler("addtask", add_task_command),
        CommandHandler("addmeeting", add_meeting_command),
        CommandHandler("setprogress", set_progress_command),
        CommandHandler("addresourceall", add_resource_all_command),
        CommandHandler("addtaskall", add_task_all_command),
        CommandHandler("replydoubt", reply_doubt_command),
        CommandHandler("scheduleresource", schedule_resource_command),
        CommandHandler("scheduletask", schedule_task_command),
        CommandHandler("unregistered", unregistered_command),
        CommandHandler("reviewsubmissions", review_submissions_command),
        CommandHandler("approvetask", approve_task_command),
        CommandHandler("rejecttask", reject_task_command),
        CommandHandler("adminhelp", admin_help_command),
    ]
