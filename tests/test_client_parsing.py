import email
from mailcleaner.client import _clean_header, _extract_text_body


def test_clean_header_decoding():
    raw_header = "=?UTF-8?B?U3VwZXIgRGVhbHMhIQ==?="
    assert _clean_header(raw_header) == "Super Deals!!"


def test_extract_text_body_multipart():
    raw_mime = (
        b"From: sender@example.com\r\n"
        b"Subject: Test MIME\r\n"
        b"MIME-Version: 1.0\r\n"
        b'Content-Type: multipart/alternative; boundary="boundary-string"\r\n\r\n'
        b"--boundary-string\r\n"
        b"Content-Type: text/plain; charset=utf-8\r\n\r\n"
        b"This is the plaintext content.\r\n"
        b"--boundary-string\r\n"
        b"Content-Type: text/html; charset=utf-8\r\n\r\n"
        b"<p>This is HTML content.</p>\r\n"
        b"--boundary-string--\r\n"
    )

    msg = email.message_from_bytes(raw_mime)
    extracted = _extract_text_body(msg)
    assert extracted == "This is the plaintext content."