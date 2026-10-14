from enum import Enum
from typing import Any, Dict


class Action(str, Enum):
    ARCHIVE = "archieve"
    DELETE = "delete"
    MOVE_RECEIPTS = 'receipts'
    MOVE_NEWSLETTERS = "newsletters"
    MOVE_NOTIFICATIONS = "notifications"
    KEEP_INBOX = "inbox"


"""Configuration and classification taxonomy for MailCleaner."""

from enum import Enum
from typing import Any, Dict, List


class Action(str, Enum):
    DELETE = "delete"
    MOVE_RECEIPTS = "receipts"
    MOVE_NEWSLETTERS = "newsletters"
    MOVE_NOTIFICATIONS = "notifications"
    KEEP_INBOX = "inbox"


CRITICAL_SAFETY_KEYWORDS: List[str] = [
    "security alert",
    "verification code",
    "2-step verification",
    "password reset",
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
