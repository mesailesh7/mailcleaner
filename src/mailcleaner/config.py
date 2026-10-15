from enum import Enum
import os
from pathlib import Path
from typing import Any, Dict, List

APP_DIR = Path.home() / ".mailcleaner"
CONFIG_FILE = APP_DIR / "config.json"
RULES_FILE = APP_DIR / "rules.json"
KEY_FILE = APP_DIR / ".key"

class Action(str, Enum):
    DELETE = "delete"
    MOVE_RECEIPTS = "receipts"
    MOVE_NEWSLETTERS = "newsletters"
    MOVE_NOTIFICATIONS = "notifications"
    KEEP_INBOX = "inbox"
    CUSTOM_MOVE = "custom_move"

DEFAULT_FOLDER_MAP: Dict[str, str] = {
    Action.MOVE_RECEIPTS.value: "Receipts",
    Action.MOVE_NEWSLETTERS.value: "Newsletters",
    Action.MOVE_NOTIFICATIONS.value: "Notifications",
}

PROVIDER_PRESETS: Dict[str, Dict[str, Any]] = {
    "gmail": {
        "name": "Gmail / Google Workspace",
        "host": "imap.gmail.com",
        "port": 993,
        "ssl": True,
        "hint": "Use your Gmail address and a 16-character Google App Password (generated in Google Account Security).",
    },
    "icloud": {
        "name": "iCloud Mail",
        "host": "imap.mail.me.com",
        "port": 993,
        "ssl": True,
        "hint": "Use your Apple ID email and an App-Specific Password (generated at appleid.apple.com).",
    },
    "outlook": {
        "name": "Outlook / Hotmail / Office 365",
        "host": "outlook.office365.com",
        "port": 993,
        "ssl": True,
        "hint": "Use your Microsoft account email and an App Password or account password with IMAP enabled.",
    },
    "yahoo": {
        "name": "Yahoo Mail",
        "host": "imap.mail.yahoo.com",
        "port": 993,
        "ssl": True,
        "hint": "Use your Yahoo email and an App Password generated in Yahoo Account Security.",
    },
    "fastmail": {
        "name": "Fastmail",
        "host": "imap.fastmail.com",
        "port": 993,
        "ssl": True,
        "hint": "Use your Fastmail email and an App Password with Mail access.",
    },
    "custom": {
        "name": "Custom IMAP Server",
        "host": "",
        "port": 993,
        "ssl": True,
        "hint": "Specify any custom IMAP server host and port.",
    },
}

CRITICAL_SAFETY_KEYWORDS: List[str] = [
    "security alert",
    "verification code",
    "2-step verification",
    "password reset",
    "one-time password",
    "authentication code",
    "no-reply@accounts.google.com",
    "appleid@id.apple.com",
    "job alert",
]

EMAIL_DECISION_QUESTIONS: Dict[str, Dict[str, Any]] = {
    "is_spam": {
        "type": "noul",
        "instructions": "Is this email unwanted marketing spam, promotional blast, scam, giveaway, cold sales pitch, or junk?",
    },
    "category": {
        "type": "choice",
        "instructions": "What is the core functional category of this legitimate email?",
        "criteria": {
            Action.MOVE_RECEIPTS.value: "Invoices, billing statements, purchase receipts, order tracking, shipping updates, payment confirmations",
            Action.MOVE_NEWSLETTERS.value: "Subscribed newsletters, periodic industry digests, blog digests, long-form community updates",
            Action.MOVE_NOTIFICATIONS.value: "Automated alerts from software tools, GitHub/Jira activity, server alerts, verification codes, security alerts",
            Action.KEEP_INBOX.value: "Direct personal or professional correspondence written by a real individual specifically to the recipient",
        },
    },
}
