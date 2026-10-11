# from typing import Dict, Optional
# from laya import Router
# from mailcleaner.config import EMAIL_DECISION_QUESTIONS, Action
#
#
# class EmailClassifier:
#     def __init__(self, preload: bool = False):
#         """
#         Initialize Laya Router.
#                 Args:
#                     preload: If True, preloads checkpoints into memory upfront.
#                 """
#
#         self.router = Router(preload=preload)
#         self.questions = EMAIL_DECISION_QUESTIONS
#
#     def classifiy_email(self, subject: str, sender: str, body: str) -> Dict[str, any]:
#         """Classify an email state in a single forward pass.
#
#                 Formats the message as an informational state document.
#                 """
#         truncated_body = body[:2000] if body else ""
#
#         state = (
#             f"Sender: {sender} \n",
#             f"Subject: {subject} \n",
#             f"Content: {truncated_body} \n",
#         )
#
#         result = self.router.predict(state, self.questions)
#
#         action = result["answers"]["action"]["choice"]
#         junk_prob = result["answers"]["is_junk"]["noul"]
#
#         return {
#             "action": Action(action),
#             "junk_prob": float(junk_prob),
#             "model_used": result.get("routing", {}).get("model", "local")
#         }

"""Laya-powered local decision engine."""

from typing import Any, Dict
from laya import Router
from mailcleaner.config import EMAIL_DECISION_QUESTIONS, Action


class EmailClassifier:
    def __init__(self, preload: bool = False, spam_threshold: float = 0.60):
        self.router = Router(preload=preload)
        self.questions = EMAIL_DECISION_QUESTIONS
        self.spam_threshold = spam_threshold

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
        if spam_prob >= self.spam_threshold:
            action = Action.DELETE
        else:
            action = Action(category_choice)

        return {
            "action": action,
            "junk_probability": spam_prob,
            "category": category_choice,
            "model_used": result.get("routing", {}).get("model", "local"),
        }
