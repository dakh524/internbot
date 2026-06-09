# 🤖 InternBot — Telegram Internship Management Bot

A Telegram bot that manages internship workflows by integrating with Google Sheets. Interns verify their Gmail, access resources, submit work, ask doubts, and track progress — all from Telegram.

---

## 📁 Project Structure

```
internbot/
├── bot/
│   ├── __init__.py          # Package marker
│   ├── main.py              # Entry point — run this
│   ├── config.py            # Environment variable loader
│   ├── sheets.py            # Google Sheets integration (gspread)
│   ├── keyboards.py         # Inline keyboard layouts
│   └── handlers/
│       ├── __init__.py      # Package marker
│       ├── start.py         # /start & Gmail verification flow
│       ├── menu.py          # Main menu & feature handlers
│       └── admin.py         # Admin commands (/broadcast, /interns, /stats)
├── credentials.json         # Google Service Account key (YOU provide this)
├── .env.example             # Environment variable template
├── .gitignore
├── requirements.txt
└── README.md
```

---

## 🚀 Quick Start

### 1. Prerequisites

- **Python 3.10+**
- A **Telegram Bot Token** from [@BotFather](https://t.me/BotFather)
- A **Google Cloud Service Account** with Sheets API enabled
- Your **Google Sheet** shared with the service account email

### 2. Clone & Install

```bash
cd internbot
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux

pip install -r requirements.txt
```

### 3. Configure Environment

```bash
copy .env.example .env       # Windows
# cp .env.example .env       # macOS/Linux
```

Edit `.env` and fill in:

| Variable | Description |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Bot token from @BotFather |
| `GOOGLE_SHEET_ID` | ID from your Google Sheet URL |
| `GOOGLE_CREDENTIALS_PATH` | Path to `credentials.json` |
| `ADMIN_IDS` | Comma-separated Telegram user IDs for admins |

### 4. Set Up Google Sheet

Your Google Sheet should have these column headers in **Row 1**:

| A | B | C | D | E | F | G | H | I | J | K | L |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Name | Gmail | Offer Status | Telegram ID | Domain | Tasks | Submitted Work | Doubts | Meetings | Progress | Certificate Status | Resources |

**Important:** Share the spreadsheet with your service account email (found in `credentials.json` → `client_email`).

### 5. Run the Bot

```bash
python -m bot.main
```

---

## 🎮 Bot Commands

### Intern Commands

| Command | Description |
|---|---|
| `/start` | Begin Gmail verification |
| `/menu` | Show the main menu |
| `/cancel` | Cancel current operation |

### Menu Options

| Button | Action |
|---|---|
| 📚 Resources | View learning resources |
| 📝 Tasks | View assigned tasks |
| 📤 Submit Work | Submit completed work |
| ❓ Ask Doubt | Ask a question |
| 📅 Meetings | View meeting schedule |
| 📊 Progress | Check your progress |
| 🎓 Certificate | View certificate status |

### Admin Commands

| Command | Description |
|---|---|
| `/broadcast <msg>` | Send a message to all linked interns |
| `/interns` | List all interns with details |
| `/stats` | View aggregate statistics |

---

## 🔐 How Verification Works

```
User sends /start
    → Bot asks for Gmail
    → Bot searches Gmail in Google Sheet (Column B)
    → If Offer Status (Column C) == "ISSUED":
        ✅ Save Telegram ID to Column D
        ✅ Show main menu
    → Otherwise:
        ❌ Access denied with reason
```

---

## 🛠️ Google Cloud Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or use existing)
3. Enable **Google Sheets API** and **Google Drive API**
4. Create a **Service Account** under IAM & Admin
5. Generate a **JSON key** → save as `credentials.json` in the project root
6. Share your Google Sheet with the service account's email address

---

## 📝 Notes

- The bot uses `python-telegram-bot` v21+ (async)
- All data is stored in Google Sheets — no local database needed
- Admin IDs must be Telegram user IDs (numeric), not usernames
- To find your Telegram ID, use [@userinfobot](https://t.me/userinfobot)

---

## 📄 License

This project is for educational / internal use.
