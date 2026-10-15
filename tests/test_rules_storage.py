import pytest
from mailcleaner.config import Action
from mailcleaner.storage import (
    Rule,
    evaluate_manual_rules,
    match_rule_condition,
    encrypt_secret,
    decrypt_secret,
)
from mailcleaner.engine import EmailClassifier

def test_encryption_roundtrip():
    secret = "my-secure-imap-token-1234"
    encrypted = encrypt_secret(secret)
    decrypted = decrypt_secret(encrypted)
    assert decrypted == secret

def test_rule_matching_conditions():
    assert match_rule_condition("billing@company.com", "contains", "company")
    assert match_rule_condition("billing@company.com", "equals", "billing@company.com")
    assert match_rule_condition("Invoice 1234", "starts_with", "invoice")
    assert match_rule_condition("order-summary.pdf", "ends_with", ".pdf")
    assert match_rule_condition("Your verification code is 9876", "regex", r"\d{4}")

def test_evaluate_manual_rules_priority():
    rules = [
        Rule(
            name="Move Stripe to Finance",
            field="sender",
            operator="contains",
            value="stripe.com",
            action="move",
            target_folder="Finance",
        ),
        Rule(
            name="Delete Spammers",
            field="sender",
            operator="contains",
            value="spammer.xyz",
            action="delete",
        ),
    ]

    res1 = evaluate_manual_rules(rules, "support@stripe.com", "Payment received", "Body")
    assert res1 is not None
    assert res1["action"] == Action.CUSTOM_MOVE
    assert res1["target_folder"] == "Finance"

    res2 = evaluate_manual_rules(rules, "deals@spammer.xyz", "Win a boat", "Body")
    assert res2 is not None
    assert res2["action"] == Action.DELETE

    res3 = evaluate_manual_rules(rules, "friend@example.com", "Lunch", "Body")
    assert res3 is None

def test_engine_with_manual_rules():
    classifier = EmailClassifier()
    rules = [
        Rule(
            name="Custom Move Rule",
            field="subject",
            operator="contains",
            value="quarterly tax review",
            action="move",
            target_folder="Taxes/2026",
        )
    ]

    result = classifier.classify_email(
        subject="Your quarterly tax review documents",
        sender="accountant@taxfirm.com",
        body="Attached are your reports.",
        custom_rules=rules,
    )

    assert result["action"] == Action.CUSTOM_MOVE
    assert result["target_folder"] == "Taxes/2026"
    assert result["matched_rule"] == "Custom Move Rule"
