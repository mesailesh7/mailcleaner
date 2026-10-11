# import pytest
# from mailcleaner.engine import EmailClassifier
# from mailcleaner.config import Action
#
#
# @pytest.fixture(scope="module")
# def classifier():
#     return EmailClassifier()
#
#
# def test_classify_receipts(classifier):
#     result = classifier.classifiy_email(
#         subject="Your invoice for October 2026",
#         sender="billing@stripe.com",
#         body="Thank you for your payment of $49.00 USD. Your invoice is attached"
#     )
#
#     assert result["action"] == Action.MOVE_RECEIPTS
#
#
# def test_classify_spam_marketing(classifier):
#     result = classifier.classifiy_email(
#         subject="Claim your free $500 gift card today only!!!",
#         sender="exclusive-deals@randomdomain.xyz",
#         body="Click here now to claim your limited prize before it expires!",
#     )
#     assert result["action"] == Action.DELETE
#     assert result["junk_probability"] > 0.5
#
#
# def test_classify_personal_email(classifier):
#     result = classifier.classifiy_email(
#         subject="Follow up on our chat yesterday",
#         sender="sarah@example.com",
#         body="Hey, let me know if you are free for lunch tomorrow to discuss the roadmap.",
#     )
#     assert result["action"] == Action.KEEP_INBOX

import pytest
from mailcleaner.engine import EmailClassifier
from mailcleaner.config import Action


@pytest.fixture(scope="module")
def classifier():
    return EmailClassifier()


def test_classify_receipt(classifier):
    result = classifier.classify_email(
        subject="Your invoice for October 2026",
        sender="billing@stripe.com",
        body="Thank you for your payment of $49.00 USD. Your invoice is attached.",
    )
    assert result["action"] == Action.MOVE_RECEIPTS


def test_classify_spam_marketing(classifier):
    result = classifier.classify_email(
        subject="Claim your free $500 gift card today only!!!",
        sender="exclusive-deals@randomdomain.xyz",
        body="Click here now to claim your limited prize before it expires!",
    )
    assert result["action"] == Action.DELETE
    assert result["junk_probability"] >= 0.60


def test_classify_personal_email(classifier):
    result = classifier.classify_email(
        subject="Follow up on our chat yesterday",
        sender="sarah@example.com",
        body="Hey, let me know if you are free for lunch tomorrow to discuss the roadmap.",
    )
    assert result["action"] == Action.KEEP_INBOX
    assert result["junk_probability"] < 0.50
