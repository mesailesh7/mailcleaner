from enum import Enum
from typing import Any, Dict


class Action(str, Enum):
    ARCHIVE = "archieve"
    DELETE = "delete"
    MOVE_RECEIPTS = 'receipts'
    MOVE_NEWSLETTERS = "newsletters"
    MOVE_NOTIFICATIONS = "notifications"
    KEEP_INBOX = "inbox"


# EMAIL_DECISION_QUESTIONS: Dict[str, Dict[str, Any]] = {
#     "action": {
#         "type": "choice",
#         "instructions": "Determine the primary operational action to perform on this email.",
#         "criteria": {
#             Action.DELETE.value: "Marketing spam, unwanted cold outreach, expired promotions, phishing",
#             Action.MOVE_RECEIPTS.value: "Invoices, payment confirmations, subscriptions, bank notices, order delivery updates",
#             Action.MOVE_NEWSLETTERS.value: "Weekly digests, tech blogs, editorial letters, product update roundups",
#             Action.MOVE_NOTIFICATIONS.value: "Automated Jira/GitHub alerts, CI/CD notices, password reset links, system status notifications",
#             Action.KEEP_INBOX.value: "Direct personal or professional correspondence from a human requiring attention or reply",
#
#         },
#     },
#     "is_junk": {
#         "type": "noul",
#         "instructions": "Is this email unsolicited spam, low-value promotional blast, or trash?"
#     }
# }

"""Configuration and classification taxonomy for MailCleaner."""

from enum import Enum
from typing import Any, Dict


class Action(str, Enum):
    DELETE = "delete"
    MOVE_RECEIPTS = "receipts"
    MOVE_NEWSLETTERS = "newsletters"
    MOVE_NOTIFICATIONS = "notifications"
    KEEP_INBOX = "inbox"


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
