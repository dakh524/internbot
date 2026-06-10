"""
sheets.py - Google Sheets integration via gspread

Place this file at: bot/sheets.py

Handles all read/write operations against the Google Sheet.
Expected sheet columns (row 1 = headers):
    A: Name
    B: Gmail
    C: Offer Status   (e.g. "ISSUED", "PENDING", "REJECTED")
    D: Telegram ID
    E: Domain / Role
    F: Tasks
    G: Submitted Work
    H: Doubts
    I: Meetings
    J: Progress
    K: Certificate Status
    L: Resources
"""

from __future__ import annotations

import json
import logging
import gspread
from google.oauth2.service_account import Credentials

from bot.config import GOOGLE_CREDENTIALS_PATH, GOOGLE_SHEET_ID, GOOGLE_CREDENTIALS_JSON

logger = logging.getLogger(__name__)

# Google API scopes required for Sheets access
_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# Module-level worksheet handle (initialized lazily)
_worksheet: gspread.Worksheet | None = None


def _get_worksheet() -> gspread.Worksheet:
    """Return (and cache) the first worksheet of the configured spreadsheet."""
    global _worksheet
    if _worksheet is None:
        try:
            if GOOGLE_CREDENTIALS_JSON:
                logger.info("Initializing Google Credentials from GOOGLE_CREDENTIALS_JSON env var.")
                info = json.loads(GOOGLE_CREDENTIALS_JSON)
                creds = Credentials.from_service_account_info(info, scopes=_SCOPES)
            else:
                logger.info(f"Initializing Google Credentials from file: {GOOGLE_CREDENTIALS_PATH}")
                creds = Credentials.from_service_account_file(
                    GOOGLE_CREDENTIALS_PATH, scopes=_SCOPES
                )
            client = gspread.authorize(creds)
            spreadsheet = client.open_by_key(GOOGLE_SHEET_ID)
            _worksheet = spreadsheet.sheet1  # Uses the first sheet
            logger.info("Successfully connected to Google Sheet.")
        except Exception as e:
            logger.error(f"Failed to connect to Google Sheet: {e}", exc_info=True)
            raise e
    return _worksheet


def refresh_connection() -> None:
    """Force a fresh connection on next call (useful after token expiry)."""
    global _worksheet
    _worksheet = None


# ---------------------------------------------------------------------------
# Read helpers
# ---------------------------------------------------------------------------


# The columns the bot actually reads — passed to get_all_records() so gspread
# doesn't crash when the sheet contains duplicate or unexpected header names.
# NOTE: These must EXACTLY match the header row in the Google Sheet (case-sensitive).
_EXPECTED_HEADERS = [
    "Name", "gmail", "Domain", "Offer Status", "Task",
    "Resource Link", "Progress", "Certificate Approved", "Certificate Serial",
    "Telegram ID", "Submitted Work", "Doubts", "Meetings",
    "NAME (CERTIFICATE)", "College Name", "Project Title",
    "Completion Date", "Certificate Serial No", "Certificate Status",
    "Certificate URL",
]


def get_all_records() -> list[dict]:
    """Return every row as a list of dicts (header → value)."""
    ws = _get_worksheet()
    try:
        return ws.get_all_records(
            expected_headers=_EXPECTED_HEADERS,
            numericise_ignore=["all"],   # Keep IDs/serials as strings
        )
    except Exception:
        # Fall back when the sheet is missing some expected headers
        # (e.g. certificate columns not yet added) or on older gspread versions.
        try:
            return ws.get_all_records(numericise_ignore=["all"])
        except Exception:
            return ws.get_all_records()



def _get_gmail_from_record(record: dict) -> str:
    """Return the gmail value from a record, handling both 'gmail' and 'Gmail' header variants."""
    return str(record.get("gmail") or record.get("Gmail") or "").strip()


def find_intern_by_gmail(gmail: str) -> dict | None:
    """
    Look up a single intern row by Gmail address (case-insensitive).
    Returns the row as a dict, or None if not found.
    """
    records = get_all_records()
    for record in records:
        sheet_gmail = _get_gmail_from_record(record).lower()
        if sheet_gmail == gmail.strip().lower():
            return record
    return None


def find_intern_by_telegram_id(telegram_id: int) -> dict | None:
    """
    Look up a single intern row by Telegram ID.
    Returns the row as a dict, or None if not found.
    Used to skip re-verification for already-linked users.
    """
    records = get_all_records()
    for record in records:
        stored_id = str(record.get("Telegram ID", "")).strip()
        if stored_id == str(telegram_id):
            return record
    return None


def get_intern_row_number(gmail: str) -> int | None:
    """
    Return the 1-based row number for the given Gmail.
    Row 1 is the header, so data starts at row 2.
    """
    ws = _get_worksheet()
    try:
        cell = ws.find(gmail, in_column=1, case_sensitive=False)
        return cell.row if cell else None
    except Exception:
        return None


def get_telegram_id_by_gmail(gmail: str) -> int | None:
    """Return the Telegram ID of the intern if linked, else None."""
    record = find_intern_by_gmail(gmail)
    if record:
        tg_id = str(record.get("Telegram ID", "")).strip()
        if tg_id.isdigit():
            return int(tg_id)
    return None


# ---------------------------------------------------------------------------
# Write helpers
# ---------------------------------------------------------------------------

def save_telegram_id(gmail: str, telegram_id: int) -> bool:
    """
    Write the user's Telegram ID into column D of their row.
    Returns True on success.
    """
    row = get_intern_row_number(gmail)
    if row is None:
        return False
    ws = _get_worksheet()
    ws.update_cell(row, 10, str(telegram_id))  # Column J = 10
    return True


def submit_work(gmail: str, submission_text: str) -> bool:
    """
    Append submission text to the 'Submitted Work' column (G).
    Keeps previous submissions separated by newlines.
    """
    row = get_intern_row_number(gmail)
    if row is None:
        return False
    ws = _get_worksheet()
    existing = ws.cell(row, 11).value or ""  # Column K = 11
    updated = f"{existing}\n{submission_text}".strip() if existing else submission_text
    ws.update_cell(row, 11, updated)
    return True


def submit_doubt(gmail: str, doubt_text: str) -> bool:
    """
    Append a doubt to the 'Doubts' column (H).
    """
    row = get_intern_row_number(gmail)
    if row is None:
        return False
    ws = _get_worksheet()
    existing = ws.cell(row, 12).value or ""  # Column L = 12
    updated = f"{existing}\n{doubt_text}".strip() if existing else doubt_text
    ws.update_cell(row, 12, updated)
    return True


def set_intern_field(gmail: str, column: int, value: str, append: bool = False) -> bool:
    """
    Set or append a value in a specific column for an intern.
    column: 1-based column number.
    If append=True, the value is appended (newline-separated) to existing content.
    """
    row = get_intern_row_number(gmail)
    if row is None:
        return False
    ws = _get_worksheet()
    if append:
        existing = ws.cell(row, column).value or ""
        value = f"{existing}\n{value}".strip() if existing else value
    ws.update_cell(row, column, value)
    return True


def set_intern_resource(gmail: str, resource_text: str) -> bool:
    """Add/append resource info to column F (Resource Link) for an intern."""
    return set_intern_field(gmail, 6, resource_text, append=True)


def set_intern_task(gmail: str, task_text: str) -> bool:
    """Add/append a task to column E (Task) for an intern."""
    return set_intern_field(gmail, 5, task_text, append=True)


def set_intern_meeting(gmail: str, meeting_text: str) -> bool:
    """Add/append meeting info to column M (Meetings) for an intern. Assumes M is added by user."""
    return set_intern_field(gmail, 13, meeting_text, append=True)


def set_intern_progress(gmail: str, progress_text: str) -> bool:
    """Set progress in column G (Progress) for an intern."""
    return set_intern_field(gmail, 7, progress_text, append=False)


def get_all_gmails() -> list[str]:
    """Return a list of all intern Gmail addresses (for admin autocomplete)."""
    records = get_all_records()
    return [_get_gmail_from_record(r) for r in records if _get_gmail_from_record(r)]


# ---------------------------------------------------------------------------
# Data accessors for menu features
# ---------------------------------------------------------------------------

def get_intern_data(gmail: str, column_name: str) -> str:
    """
    Generic accessor: return the value of *column_name* for the intern
    identified by *gmail*. Returns a user-friendly message if empty.
    """
    record = find_intern_by_gmail(gmail)
    if record is None:
        return "❌ Your record was not found."
    value = str(record.get(column_name, "")).strip()
    return value if value else f"📭 No {column_name} data available yet."


def get_all_interns_summary() -> list[dict]:
    """Return a lightweight summary of every intern (for /interns)."""
    records = get_all_records()
    return [
        {
            "Name": r.get("Name", "N/A"),
            "Gmail": _get_gmail_from_record(r) or "N/A",
            "Offer Status": r.get("Offer Status", "N/A"),
            "Telegram ID": r.get("Telegram ID", "N/A"),
            "Domain": r.get("Domain", "N/A"),
        }
        for r in records
    ]


def get_stats() -> dict:
    """Aggregate stats for the /stats admin command."""
    records = get_all_records()
    total = len(records)
    issued = sum(
        1 for r in records
        if str(r.get("Offer Letter Status", r.get("Offer Status", ""))).strip().upper() == "ISSUED"
    )
    linked = sum(1 for r in records if str(r.get("Telegram ID", "")).strip())
    return {
        "total_interns": total,
        "offers_issued": issued,
        "telegram_linked": linked,
        "pending": total - issued,
    }


# ---------------------------------------------------------------------------
# Unregistered Visitors (Sheet tab: "Unregistered Visitors")
# ---------------------------------------------------------------------------

_unregistered_ws: gspread.Worksheet | None = None


def _get_unregistered_worksheet() -> gspread.Worksheet:
    """Return (and cache) the 'Sheet2' worksheet for unregistered visitors."""
    global _unregistered_ws
    if _unregistered_ws is not None:
        return _unregistered_ws

    try:
        if GOOGLE_CREDENTIALS_JSON:
            logger.info("Initializing Google Credentials for unregistered visitors from GOOGLE_CREDENTIALS_JSON env var.")
            info = json.loads(GOOGLE_CREDENTIALS_JSON)
            creds = Credentials.from_service_account_info(info, scopes=_SCOPES)
        else:
            logger.info(f"Initializing Google Credentials for unregistered visitors from file: {GOOGLE_CREDENTIALS_PATH}")
            creds = Credentials.from_service_account_file(
                GOOGLE_CREDENTIALS_PATH, scopes=_SCOPES
            )
        client = gspread.authorize(creds)
        spreadsheet = client.open_by_key(GOOGLE_SHEET_ID)
        # Use the existing Sheet2 tab
        _unregistered_ws = spreadsheet.worksheet("Sheet2")
        logger.info("Successfully connected to Google Sheet tab 'Sheet2'.")
    except Exception as e:
        logger.error(f"Failed to connect to unregistered visitors worksheet: {e}", exc_info=True)
        raise e
    return _unregistered_ws


def log_unregistered_visitor(
    gmail: str,
    telegram_id: int,
    telegram_username: str | None = None,
    full_name: str | None = None,
) -> bool:
    """
    Log an unregistered user's details to Sheet2.
    Prevents duplicate entries for the same Gmail.
    Returns True if a new row was added, False if already logged.
    """
    import datetime

    ws = _get_unregistered_worksheet()

    # Check for duplicate — don't log the same Gmail twice
    try:
        existing = ws.find(gmail, in_column=1, case_sensitive=False)
        if existing:
            return False  # Already logged
    except Exception:
        pass  # Not found, proceed to add

    now = datetime.datetime.now()
    row = [
        gmail,
        str(telegram_id),
        telegram_username or "N/A",
        full_name or "N/A",
        now.strftime("%Y-%m-%d"),
        now.strftime("%H:%M:%S"),
    ]
    ws.append_row(row, value_input_option="USER_ENTERED")
    return True


def get_unregistered_visitors() -> list[dict]:
    """Return all unregistered visitor records from Sheet2."""
    ws = _get_unregistered_worksheet()
    return ws.get_all_records()


# ---------------------------------------------------------------------------
# Certificate Management
# ---------------------------------------------------------------------------

def get_certificate_data(gmail: str) -> dict | None:
    """
    Get all certificate related fields for a given gmail.
    """
    record = find_intern_by_gmail(gmail)
    if not record:
        return None

    def get_val(keys: list[str]) -> str:
        for k in keys:
            for rk in record.keys():
                if rk.strip().lower() == k.lower():
                    return str(record[rk]).strip()
        return ""

    return {
        "name_certificate": get_val(["NAME (CERTIFICATE)", "Name (Certificate)", "NAME"]),
        "college_name": get_val(["College Name", "College"]),
        "project_title": get_val(["Project Title", "Project"]),
        "completion_date": get_val(["Completion Date", "Date"]),
        "serial_number": get_val(["Certificate Serial No", "Certificate Serial Number", "Serial Number", "Serial"]),
        "status": get_val(["Certificate Status", "Status"]),
        "url": get_val(["Certificate URL", "URL", "Certificate Link"]),
    }


def generate_next_serial_number() -> str:
    """
    Generate next certificate serial number of format DAKH-YYYY-XXXX.
    """
    import datetime
    import re
    year = datetime.datetime.now().year
    prefix = f"DAKH-{year}-"

    records = get_all_records()
    max_seq = 0
    pattern = re.compile(rf"DAKH-{year}-(\d{{4}})")

    for r in records:
        # Check both the specific key and other potential column matching
        serial = ""
        for k in ["Certificate Serial No", "Certificate Serial Number", "Serial Number", "Serial"]:
            for rk in r.keys():
                if rk.strip().lower() == k.lower():
                    serial = str(r[rk]).strip()
                    break
            if serial:
                break

        match = pattern.match(serial)
        if match:
            seq = int(match.group(1))
            if seq > max_seq:
                max_seq = seq

    next_seq = max_seq + 1
    return f"{prefix}{next_seq:04d}"


def save_certificate_details(gmail: str, name_cert: str, college: str) -> str | None:
    """
    Save certificate name and college name for the intern.
    Also automatically generates a serial number if it doesn't exist yet,
    and sets the status to 'PENDING' if not already set.
    Returns the generated serial number (or existing serial number), or None on failure.
    """
    row = get_intern_row_number(gmail)
    if row is None:
        return None

    ws = _get_worksheet()

    # Columns:
    # N = 14 (NAME (CERTIFICATE))
    # O = 15 (College Name)
    # R = 18 (Certificate Serial Number)
    # S = 19 (Certificate Status)
    
    # Read cells first to check if they already exist
    try:
        serial_val = ws.cell(row, 18).value
    except Exception:
        serial_val = None

    try:
        status_val = ws.cell(row, 19).value
    except Exception:
        status_val = None

    if not serial_val or not str(serial_val).strip():
        serial_val = generate_next_serial_number()

    if not status_val or not str(status_val).strip() or str(status_val).strip().upper() not in ["GENERATED", "PENDING"]:
        status_val = "PENDING"

    ws.update_cell(row, 14, name_cert)  # N = NAME (CERTIFICATE)
    ws.update_cell(row, 15, college)    # O = College Name
    ws.update_cell(row, 18, str(serial_val))  # R = Certificate Serial Number
    ws.update_cell(row, 19, str(status_val))  # S = Certificate Status

    return str(serial_val)


# ---------------------------------------------------------------------------
# Task Submission System (Columns: V=Submission Link, W=Date, X=Status, Y=Remarks)
# ---------------------------------------------------------------------------

def get_task_submission_data(gmail: str) -> dict | None:
    """
    Get task submission related fields: Task, Submission Link, Date, Status, Remarks.
    """
    record = find_intern_by_gmail(gmail)
    if not record:
        return None

    def get_val(keys: list[str]) -> str:
        for k in keys:
            for rk in record.keys():
                if rk.strip().lower() == k.lower():
                    return str(record[rk]).strip()
        return ""

    return {
        "task": get_val(["Task", "Tasks"]),
        "submission_link": get_val(["Submission Link", "Submission URL", "Submitted URL"]),
        "date": get_val(["Date", "Submission Date", "Date of Attempt"]),
        "status": get_val(["Status", "Submission Status"]),
        "remarks": get_val(["Remarks", "Admin Remarks", "Mentor Remarks"]),
        "progress": get_val(["Progress", "Current Progress"]),
        "name": record.get("Name", "Intern"),
    }


def save_task_submission(gmail: str, link: str, status: str = "SUBMITTED") -> bool:
    """
    Save/overwrite task submission details:
    Column V (22) = link
    Column W (23) = current date & time (YYYY-MM-DD HH:MM)
    Column X (24) = status
    """
    row = get_intern_row_number(gmail)
    if row is None:
        return False

    ws = _get_worksheet()
    import datetime
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    # Column V = 22, W = 23, X = 24
    ws.update_cell(row, 22, link)
    ws.update_cell(row, 23, now)
    ws.update_cell(row, 24, status)
    return True


def update_task_status_in_sheet(gmail: str, status: str, remarks: str = "") -> bool:
    """
    Update Task status (Column X = 24) and remarks (Column Y = 25).
    If status is APPROVED, automatically increments Progress (Column G = 7) by 25%.
    """
    row = get_intern_row_number(gmail)
    if row is None:
        return False

    ws = _get_worksheet()
    ws.update_cell(row, 24, status)
    if remarks:
        ws.update_cell(row, 25, remarks)

    if status.upper() == "APPROVED":
        # Automatically update Progress Column G (7)
        try:
            curr_progress = ws.cell(row, 7).value or "0%"
        except Exception:
            curr_progress = "0%"

        import re
        nums = re.findall(r"\d+", str(curr_progress))
        curr_val = int(nums[0]) if nums else 0
        new_val = min(curr_val + 25, 100)
        ws.update_cell(row, 7, f"{new_val}%")

    return True


def get_submitted_tasks() -> list[dict]:
    """
    Get all intern submissions with status = 'SUBMITTED'
    """
    records = get_all_records()
    submitted = []

    for record in records:
        gmail = _get_gmail_from_record(record)
        name = str(record.get("Name", "")).strip()

        status = ""
        task = ""
        link = ""
        date = ""

        for k in record.keys():
            kl = k.strip().lower()
            if kl in ["status", "submission status"]:
                status = str(record[k]).strip()
            elif kl in ["task", "tasks"]:
                task = str(record[k]).strip()
            elif kl in ["submission link", "submission url", "submitted url"]:
                link = str(record[k]).strip()
            elif kl in ["date", "submission date"]:
                date = str(record[k]).strip()

        if status.upper() == "SUBMITTED":
            submitted.append({
                "gmail": gmail,
                "name": name,
                "task": task,
                "link": link,
                "date": date,
            })
    return submitted


def is_eligible_for_certificate(gmail: str) -> tuple[bool, str]:
    """
    Check if intern is eligible for certificate.
    Returns (eligible, reason).
    """
    data = get_task_submission_data(gmail)
    if not data:
        return False, "Intern record not found."

    task = data.get("task", "").strip()
    link = data.get("submission_link", "").strip()
    status = data.get("status", "").strip().upper()

    if not task:
        return False, "No tasks have been assigned to you yet."
    if not link:
        return False, "You have not submitted your task yet."
    if status != "APPROVED":
        return False, f"Your task submission status is {status or 'PENDING'}. It must be APPROVED."

    return True, ""


