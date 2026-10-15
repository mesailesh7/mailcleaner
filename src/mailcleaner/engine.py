from typing import Any, Callable, Dict, List, Optional
from laya import Router
from mailcleaner.config import EMAIL_DECISION_QUESTIONS, Action, CRITICAL_SAFETY_KEYWORDS
from mailcleaner.storage import Rule, evaluate_manual_rules

class EmailClassifier:
    def __init__(
        self,
        preload: bool = False,
        spam_threshold: float = 0.60,
        status_callback: Optional[Callable[[str], None]] = None,
    ):
        if status_callback and preload:
            status_callback("Initializing and preloading local classification engine...")
        self.router = Router(preload=preload)
        if status_callback and preload:
            status_callback("Local classification engine ready.")
        self.questions = EMAIL_DECISION_QUESTIONS
        self.spam_threshold = spam_threshold

    def _is_critical_message(self, sender: str, subject: str) -> bool:
        target = f"{sender} {subject}".lower()
        return any(keyword in target for keyword in CRITICAL_SAFETY_KEYWORDS)

    def classify_email(
        self,
        subject: str,
        sender: str,
        body: str,
        custom_rules: Optional[List[Rule]] = None,
    ) -> Dict[str, Any]:
        if custom_rules:
            rule_match = evaluate_manual_rules(custom_rules, sender, subject, body)
            if rule_match:
                action = rule_match["action"]
                is_del = action == Action.DELETE
                return {
                    "action": action,
                    "junk_probability": 1.0 if is_del else 0.0,
                    "category": rule_match.get("target_folder") or action.value,
                    "model_used": f"Rule: {rule_match['rule_name']}",
                    "matched_rule": rule_match["rule_name"],
                    "target_folder": rule_match.get("target_folder"),
                }

        truncated_body = body[:2000] if body else ""
        state = (
            f"From: {sender}\n"
            f"Subject: {subject}\n\n"
            f"{truncated_body}"
        )

        result = self.router.predict(state, self.questions)

        spam_prob = float(result["answers"]["is_spam"]["noul"])
        category_choice = result["answers"]["category"]["choice"]

        if self._is_critical_message(sender, subject):
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
            "matched_rule": None,
            "target_folder": None,
        }
