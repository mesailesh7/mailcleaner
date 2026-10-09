from enum import Enum
from typing import Any, Dict


class Action(str, Enum):
    ARCHIVE = "archieve"
    DELETE = "delete"
    MOVE_RECEIPTS = 'receipts'
    MOVE_NEWSLETTERS = "newsletters"
    MOVE_NOTIFICATIONS = "notifications"
    KEEP_INBOX = "inbox"


EMAIL_DECISION_QUESTIONS: Dict[str, Dict[str, Any]] = {
    "action": {
        "type": "choice",
        "instructions": "Determine the primary operational action to perform on this email.",
        "criteria": {
            Action.DELETE.value: "Marketing spam, unwanted cold outreach, expired promotions, phishing",
            Action.MOVE_RECEIPTS.value: "Invoices, payment confirmations, subscriptions, bank notices, order delivery updates",
            Action.MOVE_NEWSLETTERS.value: "Weekly digests, tech blogs, editorial letters, product update roundups",
            Action.MOVE_NOTIFICATIONS.value: "Automated Jira/GitHub alerts, CI/CD notices, password reset links, system status notifications",
            Action.KEEP_INBOX.value: "Direct personal or professional correspondence from a human requiring attention or reply",

        },
    },
    "is_junk": {
        "type": "noul",
        "instructions": "Is this email unsolicited spam, low-value promotional blast, or trash?"
    }

}
