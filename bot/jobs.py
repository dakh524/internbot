"""
jobs.py - Background task scheduler

Place this file at: bot/jobs.py

Handles:
1. Daily morning Tech/Education Tip (9:00 AM)
2. Daily evening Task Progress Reminder (6:00 PM)
3. Scheduled resource/task delivery
"""

import logging
import datetime
import random

from telegram.ext import ContextTypes

from bot import sheets

logger = logging.getLogger(__name__)

# Sample tech tips for the morning broadcast
TECH_TIPS = [
    "💡 *Tech Tip:* Always document your code. Your future self will thank you!",
    "💡 *Tech Tip:* Use meaningful variable names. Code is read much more often than it is written.",
    "💡 *Tech Tip:* Break complex problems into smaller, manageable functions.",
    "💡 *Tech Tip:* Don't reinvent the wheel. Check if a library already solves your problem.",
    "💡 *Tech Tip:* Version control is your friend. Commit early and often.",
    "💡 *Tech Tip:* Learn keyboard shortcuts for your IDE. It saves hours of time.",
    "💡 *Tech Tip:* Test your edge cases, not just the happy path.",
    "💡 *Tech Tip:* Keep your functions pure when possible to avoid side effects.",
    "💡 *Tech Tip:* Read error messages carefully. They usually tell you exactly what's wrong.",
    "💡 *Tech Tip:* Stay curious. Technology changes fast, keep learning!"
]


# ---------------------------------------------------------------------------
# Daily Jobs
# ---------------------------------------------------------------------------

async def morning_tip_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a random tech tip to all verified interns every morning."""
    logger.info("Running morning_tip_job")
    tip = random.choice(TECH_TIPS)
    
    records = sheets.get_all_records()
    sent_count = 0
    
    for record in records:
        tg_id = str(record.get("Telegram ID", "")).strip()
        if not tg_id or not tg_id.isdigit():
            continue
            
        try:
            await context.bot.send_message(
                chat_id=int(tg_id),
                text=f"🌅 *Good Morning!* Here is your daily tip:\n\n{tip}",
                parse_mode="Markdown",
            )
            sent_count += 1
        except Exception as e:
            logger.error(f"Failed to send morning tip to {tg_id}: {e}")
            
    logger.info(f"Morning tip sent to {sent_count} interns.")


async def progress_reminder_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Remind interns with assigned tasks to update their progress."""
    logger.info("Running progress_reminder_job")
    
    records = sheets.get_all_records()
    sent_count = 0
    
    for record in records:
        tg_id = str(record.get("Telegram ID", "")).strip()
        if not tg_id or not tg_id.isdigit():
            continue
            
        # Only remind if they actually have a task assigned
        task = str(record.get("Task", "")).strip()
        if not task:
            continue
            
        try:
            await context.bot.send_message(
                chat_id=int(tg_id),
                text=(
                    "🔔 *Progress Reminder*\n\n"
                    "You have an active task:\n"
                    f"📝 _{task}_\n\n"
                    "Please remember to update your progress today! Use the menu or send /menu."
                ),
                parse_mode="Markdown",
            )
            sent_count += 1
        except Exception as e:
            logger.error(f"Failed to send progress reminder to {tg_id}: {e}")
            
    logger.info(f"Progress reminder sent to {sent_count} interns.")


# ---------------------------------------------------------------------------
# Dynamic Jobs (Scheduled by Admin)
# ---------------------------------------------------------------------------

async def deliver_scheduled_message_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Delivers a specific scheduled message (Resource or Task) to a specific user.
    Job context should contain: {'gmail': '...', 'tg_id': 123, 'type': 'Resource|Task', 'text': '...'}
    """
    job_data = context.job.data
    gmail = job_data['gmail']
    tg_id = job_data['tg_id']
    msg_type = job_data['type']
    text = job_data['text']
    
    # Send the Telegram message
    try:
        emoji = "📚" if msg_type == "Resource" else "📝"
        await context.bot.send_message(
            chat_id=tg_id,
            text=f"🆕 *New {msg_type} Assigned!*\n\n{emoji} {text}",
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.error(f"Failed to deliver scheduled {msg_type} to {gmail} ({tg_id}): {e}")
        
    # Update the Google Sheet
    try:
        if msg_type == "Resource":
            sheets.set_intern_resource(gmail, text)
        elif msg_type == "Task":
            sheets.set_intern_task(gmail, text)
    except Exception as e:
        logger.error(f"Failed to update sheet for scheduled {msg_type} for {gmail}: {e}")


def setup_daily_jobs(job_queue) -> None:
    """Register the fixed daily jobs with the JobQueue."""
    # Run morning tip at 9:00 AM daily
    t_morning = datetime.time(hour=9, minute=0, second=0)
    job_queue.run_daily(morning_tip_job, t_morning, name="morning_tip")
    
    # Run progress reminder at 6:00 PM daily
    t_evening = datetime.time(hour=18, minute=0, second=0)
    job_queue.run_daily(progress_reminder_job, t_evening, name="evening_progress")
    
    logger.info("Daily jobs registered: morning_tip (09:00), evening_progress (18:00)")
