"""
sheets.py - Google Sheets integration via gspread

Place this file at: bot/sheets.py

Handles all read/write operations against the Google Sheet.

Actual Sheet1 columns (fetched live — DO NOT EDIT without re-verifying):
    Col  1 (A): gmail
    Col  2 (B): Name
    Col  3 (C): Domain
    Col  4 (D): Offer Status
    Col  5 (E): Task
    Col  6 (F): Resource Link
    Col  7 (G): Progress
    Col  8 (H): Certificate Approved
    Col  9 (I): Certificate Serial
    Col 10 (J): Telegram ID
    Col 11 (K): Submitted Work
    Col 12 (L): Doubts
    Col 13 (M): Meetings
    Col 14 (N): NAME (CERTIFICATE)
    Col 15 (O): College Name
    Col 16 (P): Project Title
    Col 17 (Q): Completion Date
    Col 18 (R): Certificate Serial No
    Col 19 (S): Certificate Status
    Col 20 (T): Certificate URL
    Col 21 (U): [empty]
    Col 22 (V): Submission Link
    Col 23 (W): Date
    Col 24 (X): Status
    Col 25 (Y): Remarks

Sheet2 columns (Unregistered Visitors):
    Col  1 (A): Gmail they typed
    Col  2 (B): Their Telegram ID
    Col  3 (C): Their Telegram username
    Col  4 (D): Their full name (from Telegram profile)
    Col  5 (E): Date of attempt
    Col  6 (F): Time of attempt
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

# ---------------------------------------------------------------------------
# Exact column numbers (1-based) — verified against live sheet
# ---------------------------------------------------------------------------
COL_GMAIL               = 1   # A: gmail
COL_NAME                = 2   # B: Name
COL_DOMAIN              = 3   # C: Domain
COL_OFFER_STATUS        = 4   # D: Offer Status
COL_TASK                = 5   # E: Task
COL_RESOURCE_LINK       = 6   # F: Resource Link
COL_PROGRESS            = 7   # G: Progress
COL_CERT_APPROVED       = 8   # H: Certificate Approved
COL_CERT_SERIAL_OLD     = 9   # I: Certificate Serial  (legacy/admin-filled)
COL_TELEGRAM_ID         = 10  # J: Telegram ID
COL_SUBMITTED_WORK      = 11  # K: Submitted Work
COL_DOUBTS              = 12  # L: Doubts
COL_MEETINGS            = 13  # M: Meetings
COL_NAME_CERTIFICATE    = 14  # N: NAME (CERTIFICATE)
COL_COLLEGE_NAME        = 15  # O: College Name
COL_PROJECT_TITLE       = 16  # P: Project Title
COL_COMPLETION_DATE     = 17  # Q: Completion Date
COL_CERT_SERIAL_NO      = 18  # R: Certificate Serial No
COL_CERT_STATUS         = 19  # S: Certificate Status
COL_CERT_URL            = 20  # T: Certificate URL
# Col 21 (U) is empty — skip
COL_SUBMISSION_LINK     = 22  # V: Submission Link
COL_SUBMISSION_DATE     = 23  # W: Date
COL_SUBMISSION_STATUS   = 24  # X: Status
COL_REMARKS             = 25  # Y: Remarks

# Exact headers in Sheet1 row 1 — used for get_all_records(expected_headers=...)
# These MUST match the sheet exactly (case-sensitive).
_EXPECTED_HEADERS = [
    "gmail",                 # A
    "Name",                  # B
    "Domain",                # C
    "Offer Status",          # D
    "Task",                  # E
    "Resource Link",         # F
    "Progress",              # G
    "Certificate Approved",  # H
    "Certificate Serial",    # I
    "Telegram ID",           # J
    "Submitted Work",        # K
    "Doubts",                # L
    "Meetings",              # M
    "NAME (CERTIFICATE)",    # N
    "College Name",          # O
    "Project Title",         # P
    "Completion Date",       # Q
    "Certificate Serial No", # R
    "Certificate Status",    # S
    "Certificate URL",       # T
    # U is empty — omitted intentionally
    "Submission Link",       # V
    "Date",                  # W
    "Status",                # X
    "Remarks",               # Y
]

# Module-level worksheet handles (initialized lazily)
_worksheet: gspread.Worksheet | None = None
_unregistered_ws: gspread.Worksheet | None = None


# ---------------------------------------------------------------------------
# Connection helpers
# ---------------------------------------------------------------------------

def _build_client() -> gspread.Client:
    """Build and return an authorized gspread client."""
    if GOOGLE_CREDENTIALS_JSON:
        logger.info("Using GOOGLE_CREDENTIALS_JSON env var for Google auth.")
        info = json.loads(GOOGLE_CREDENTIALS_JSON)
        creds = Credentials.from_service_account_info(info, scopes=_SCOPES)
    else:
        logger.info(f"Using credentials file: {GOOGLE_CREDENTIALS_PATH}")
        creds = Credentials.from_service_account_file(
            GOOGLE_CREDENTIALS_PATH, scopes=_SCOPES
        )
    return gspread.authorize(creds)


def _get_worksheet() -> gspread.Worksheet:
    """Return (and cache) Sheet1 of the configured spreadsheet."""
    global _worksheet
    if _worksheet is None:
        try:
            client = _build_client()
            spreadsheet = client.open_by_key(GOOGLE_SHEET_ID)
            _worksheet = spreadsheet.sheet1
            logger.info("Connected to Google Sheet (Sheet1).")
        except Exception as e:
            logger.error(f"Failed to connect to Google Sheet: {e}", exc_info=True)
            raise
    return _worksheet


def _get_unregistered_worksheet() -> gspread.Worksheet:
    """Return (and cache) Sheet2 (Unregistered Visitors)."""
    global _unregistered_ws
    if _unregistered_ws is None:
        try:
            client = _build_client()
            spreadsheet = client.open_by_key(GOOGLE_SHEET_ID)
            _unregistered_ws = spreadsheet.worksheet("Sheet2")
            logger.info("Connected to Google Sheet (Sheet2).")
        except Exception as e:
            logger.error(f"Failed to connect to Sheet2: {e}", exc_info=True)
            raise
    return _unregistered_ws


def refresh_connection() -> None:
    """Force fresh connections on next call (useful after token expiry)."""
    global _worksheet, _unregistered_ws
    _worksheet = None
    _unregistered_ws = None


# ---------------------------------------------------------------------------
# Read helpers
# ---------------------------------------------------------------------------

def get_all_records() -> list[dict]:
    """Return every data row in Sheet1 as a list of dicts (header → value)."""
    ws = _get_worksheet()
    try:
        return ws.get_all_records(
            expected_headers=_EXPECTED_HEADERS,
            numericise_ignore=["all"],  # Keep IDs/serials as strings
        )
    except Exception as e:
        logger.warning(f"get_all_records with expected_headers failed ({e}), retrying without.")
        try:
            return ws.get_all_records(numericise_ignore=["all"])
        except Exception:
            return ws.get_all_records()


def _get_gmail_from_record(record: dict) -> str:
    """Return gmail from a record — handles both 'gmail' (sheet) and 'Gmail' (legacy)."""
    return str(record.get("gmail") or record.get("Gmail") or "").strip()


def find_intern_by_gmail(gmail: str) -> dict | None:
    """
    Look up a single intern row by Gmail address (case-insensitive).
    Returns the row as a dict, or None if not found.
    """
    records = get_all_records()
    target = gmail.strip().lower()
    for record in records:
        if _get_gmail_from_record(record).lower() == target:
            return record
    return None


def find_intern_by_telegram_id(telegram_id: int) -> dict | None:
    """
    Look up a single intern row by Telegram ID.
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
    Return the 1-based row number for the given Gmail (Column A).
    Row 1 is the header row, data starts at row 2.
    """
    ws = _get_worksheet()
    try:
        cell = ws.find(gmail.strip(), in_column=COL_GMAIL, case_sensitive=False)
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


def get_all_gmails() -> list[str]:
    """Return a list of all intern Gmail addresses (for admin autocomplete)."""
    records = get_all_records()
    return [_get_gmail_from_record(r) for r in records if _get_gmail_from_record(r)]


def get_intern_data(gmail: str, column_name: str) -> str:
    """
    Generic accessor: return the value of *column_name* for the intern.
    Returns a user-friendly message if empty.
    """
    record = find_intern_by_gmail(gmail)
    if record is None:
        return "❌ Your record was not found."
    value = str(record.get(column_name, "")).strip()
    return value if value else f"📭 No {column_name} data available yet."


def get_all_interns_summary() -> list[dict]:
    """Return a lightweight summary of every intern (for /interns admin command)."""
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
        if str(r.get("Offer Status", "")).strip().upper() == "ISSUED"
    )
    linked = sum(1 for r in records if str(r.get("Telegram ID", "")).strip())
    return {
        "total_interns": total,
        "offers_issued": issued,
        "telegram_linked": linked,
        "pending": total - issued,
    }


# ---------------------------------------------------------------------------
# Write helpers
# ---------------------------------------------------------------------------

def _write_cell(row: int, col: int, value: str) -> None:
    """Write a single cell. Centralised for easy retry logic in future."""
    ws = _get_worksheet()
    ws.update_cell(row, col, value)


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


def save_telegram_id(gmail: str, telegram_id: int) -> bool:
    """Write the user's Telegram ID into Column J (Telegram ID)."""
    row = get_intern_row_number(gmail)
    if row is None:
        return False
    _write_cell(row, COL_TELEGRAM_ID, str(telegram_id))
    return True


def submit_work(gmail: str, submission_text: str) -> bool:
    """Append submission text to Column K (Submitted Work)."""
    return set_intern_field(gmail, COL_SUBMITTED_WORK, submission_text, append=True)


def submit_doubt(gmail: str, doubt_text: str) -> bool:
    """Append a doubt to Column L (Doubts)."""
    return set_intern_field(gmail, COL_DOUBTS, doubt_text, append=True)


def set_intern_resource(gmail: str, resource_text: str) -> bool:
    """Append resource info to Column F (Resource Link)."""
    return set_intern_field(gmail, COL_RESOURCE_LINK, resource_text, append=True)


def set_intern_task(gmail: str, task_text: str) -> bool:
    """Append a task to Column E (Task)."""
    return set_intern_field(gmail, COL_TASK, task_text, append=True)


def set_intern_meeting(gmail: str, meeting_text: str) -> bool:
    """Append meeting info to Column M (Meetings)."""
    return set_intern_field(gmail, COL_MEETINGS, meeting_text, append=True)


def set_intern_progress(gmail: str, progress_text: str) -> bool:
    """Set progress in Column G (Progress) — overwrites, does not append."""
    return set_intern_field(gmail, COL_PROGRESS, progress_text, append=False)


# ---------------------------------------------------------------------------
# Task Submission System  (V=Submission Link, W=Date, X=Status, Y=Remarks)
# ---------------------------------------------------------------------------

def get_task_submission_data(gmail: str) -> dict | None:
    """Get task submission related fields for the given intern."""
    record = find_intern_by_gmail(gmail)
    if not record:
        return None

    return {
        "task":            str(record.get("Task", "")).strip(),
        "submission_link": str(record.get("Submission Link", "")).strip(),
        "date":            str(record.get("Date", "")).strip(),
        "status":          str(record.get("Status", "")).strip(),
        "remarks":         str(record.get("Remarks", "")).strip(),
        "progress":        str(record.get("Progress", "")).strip(),
        "resource_link":   str(record.get("Resource Link", "")).strip(),
        "name":            str(record.get("Name", "Intern")).strip(),
    }


def save_task_submission(gmail: str, link: str, status: str = "SUBMITTED") -> bool:
    """
    Save task submission details:
      Col V (22) = Submission Link
      Col W (23) = Date (YYYY-MM-DD HH:MM)
      Col X (24) = Status
    """
    row = get_intern_row_number(gmail)
    if row is None:
        return False

    import datetime
    ws = _get_worksheet()
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    ws.update_cell(row, COL_SUBMISSION_LINK, link)
    ws.update_cell(row, COL_SUBMISSION_DATE, now)
    ws.update_cell(row, COL_SUBMISSION_STATUS, status)
    return True


def update_task_status_in_sheet(gmail: str, status: str, remarks: str = "") -> bool:
    """
    Update task Status (Col X) and Remarks (Col Y).
    If APPROVED, also increments Progress (Col G) by 25%.
    """
    row = get_intern_row_number(gmail)
    if row is None:
        return False

    ws = _get_worksheet()
    ws.update_cell(row, COL_SUBMISSION_STATUS, status)
    if remarks:
        ws.update_cell(row, COL_REMARKS, remarks)

    if status.strip().upper() == "APPROVED":
        try:
            curr_progress = ws.cell(row, COL_PROGRESS).value or "0%"
        except Exception:
            curr_progress = "0%"

        import re
        nums = re.findall(r"\d+", str(curr_progress))
        curr_val = int(nums[0]) if nums else 0
        new_val = min(curr_val + 25, 100)
        ws.update_cell(row, COL_PROGRESS, f"{new_val}%")

    return True


def get_submitted_tasks() -> list[dict]:
    """Return all intern rows whose Submission Status (Col X) is 'SUBMITTED'."""
    records = get_all_records()
    submitted = []
    for record in records:
        if str(record.get("Status", "")).strip().upper() == "SUBMITTED":
            submitted.append({
                "gmail":  _get_gmail_from_record(record),
                "name":   str(record.get("Name", "")).strip(),
                "task":   str(record.get("Task", "")).strip(),
                "link":   str(record.get("Submission Link", "")).strip(),
                "date":   str(record.get("Date", "")).strip(),
            })
    return submitted


def is_eligible_for_certificate(gmail: str) -> tuple[bool, str]:
    """
    Check if intern is eligible for a certificate.
    Returns (eligible: bool, reason: str).
    """
    data = get_task_submission_data(gmail)
    if not data:
        return False, "Intern record not found."

    task   = data.get("task", "").strip()
    link   = data.get("submission_link", "").strip()
    status = data.get("status", "").strip().upper()

    if not task:
        return False, "No tasks have been assigned to you yet."
    if not link:
        return False, "You have not submitted your task yet."
    if status != "APPROVED":
        return False, f"Your task submission status is '{status or 'PENDING'}'. It must be APPROVED."

    return True, ""


# ---------------------------------------------------------------------------
# Certificate Management
# ---------------------------------------------------------------------------

def get_certificate_data(gmail: str) -> dict | None:
    """Get all certificate-related fields for the given intern."""
    record = find_intern_by_gmail(gmail)
    if not record:
        return None

    return {
        "name_certificate": str(record.get("NAME (CERTIFICATE)", "")).strip(),
        "college_name":     str(record.get("College Name", "")).strip(),
        "project_title":    str(record.get("Project Title", "")).strip(),
        "completion_date":  str(record.get("Completion Date", "")).strip(),
        "serial_number":    str(record.get("Certificate Serial No", "")).strip(),
        "status":           str(record.get("Certificate Status", "")).strip(),
        "url":              str(record.get("Certificate URL", "")).strip(),
    }


def generate_next_serial_number() -> str:
    """Generate next certificate serial number in format DAKH-YYYY-XXXX."""
    import datetime
    import re

    year = datetime.datetime.now().year
    prefix = f"DAKH-{year}-"
    pattern = re.compile(rf"DAKH-{year}-(\d{{4}})")

    records = get_all_records()
    max_seq = 0
    for r in records:
        serial = str(r.get("Certificate Serial No", "") or r.get("Certificate Serial", "")).strip()
        match = pattern.match(serial)
        if match:
            seq = int(match.group(1))
            if seq > max_seq:
                max_seq = seq

    return f"{prefix}{max_seq + 1:04d}"


def save_certificate_details(gmail: str, name_cert: str, college: str) -> str | None:
    """
    Save certificate name and college name for the intern.
    Auto-generates a serial number if absent, sets status to PENDING.
    Returns the serial number string, or None on failure.

    Writes:
      Col N (14) = NAME (CERTIFICATE)
      Col O (15) = College Name
      Col R (18) = Certificate Serial No
      Col S (19) = Certificate Status
    """
    row = get_intern_row_number(gmail)
    if row is None:
        return None

    ws = _get_worksheet()

    # Read existing serial & status
    try:
        serial_val = ws.cell(row, COL_CERT_SERIAL_NO).value
    except Exception:
        serial_val = None

    try:
        status_val = ws.cell(row, COL_CERT_STATUS).value
    except Exception:
        status_val = None

    if not serial_val or not str(serial_val).strip():
        serial_val = generate_next_serial_number()

    if not status_val or str(status_val).strip().upper() not in ("GENERATED", "PENDING"):
        status_val = "PENDING"

    ws.update_cell(row, COL_NAME_CERTIFICATE, name_cert)
    ws.update_cell(row, COL_COLLEGE_NAME, college)
    ws.update_cell(row, COL_CERT_SERIAL_NO, str(serial_val))
    ws.update_cell(row, COL_CERT_STATUS, str(status_val))

    return str(serial_val)


# ---------------------------------------------------------------------------
# Unregistered Visitors (Sheet2)
# ---------------------------------------------------------------------------

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

    # Prevent duplicate entries
    try:
        existing = ws.find(gmail, in_column=1, case_sensitive=False)
        if existing:
            return False
    except Exception:
        pass

    now = datetime.datetime.now()
    ws.append_row(
        [
            gmail,
            str(telegram_id),
            telegram_username or "N/A",
            full_name or "N/A",
            now.strftime("%Y-%m-%d"),
            now.strftime("%H:%M:%S"),
        ],
        value_input_option="USER_ENTERED",
    )
    return True


def get_unregistered_visitors() -> list[dict]:
    """Return all unregistered visitor records from Sheet2."""
    ws = _get_unregistered_worksheet()
    return ws.get_all_records()
