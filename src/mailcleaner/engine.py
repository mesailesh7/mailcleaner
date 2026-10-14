"""Laya-powered local decision engine."""

from typing import Any, Dict
from laya import Router
from mailcleaner.config import EMAIL_DECISION_QUESTIONS, Action, CRITICAL_SAFETY_KEYWORDS


class EmailClassifier:
    def __init__(self, preload: bool = False, spam_threshold: float = 0.60):
        self.router = Router(preload=preload)
        self.questions = EMAIL_DECISION_QUESTIONS
        self.spam_threshold = spam_threshold

    def _is_critical_message(self, sender: str, subject: str) -> bool:
        """Determines if the message contains sensitive security or alert markers."""
        target = f"{sender} {subject}".lower()
        return any(keyword in target for keyword in CRITICAL_SAFETY_KEYWORDS)

    def classify_email(self, subject: str, sender: str, body: str) -> Dict[str, Any]:
        """Classify an email state in a single forward pass."""
        truncated_body = body[:2000] if body else ""

        state = (
            f"From: {sender}\n"
            f"Subject: {subject}\n\n"
            f"{truncated_body}"
        )

        result = self.router.predict(state, self.questions)

        spam_prob = float(result["answers"]["is_spam"]["noul"])
        category_choice = result["answers"]["category"]["choice"]

        # High confidence junk routes immediately to delete
        if self._is_critical_message(sender, subject):
            # Never delete critical alerts - route to notifications if not personal
            action = (
                Action.KEEP_INBOX
                if category_choice == Action.KEEP_INBOX.value
                else Action.MOVE_NOTIFICATIONS
            )
        elif spam_prob >= self.spam_threshold:
            action = Action.DELETE
        else:
            action = Action(category_choice)

        return {
            "action": action,
            "junk_probability": spam_prob,
            "category": category_choice,
            "model_used": result.get("routing", {}).get("model", "local"),
        }
