"""IMAP Email Client interface for fetching, parsing, and safely sorting emails."""

import email
from email.header import decode_header
import imaplib
from typing import Generator, List, Optional
from pydantic import BaseModel


class EmailMessage(BaseModel):
    uid: str
    sender: str
    subject: str
    body: str


def _clean_header(header_value: Optional[str]) -> str:
    """Decodes MIME encoded email header fields into UTF-8 strings."""
    if not header_value:
        return ""
    decoded_fragments = decode_header(header_value)
    result = []
    for fragment, encoding in decoded_fragments:
        if isinstance(fragment, bytes):
            result.append(fragment.decode(encoding or "utf-8", errors="replace"))
        else:
            result.append(str(fragment))
    return "".join(result)


def _extract_text_body(msg: email.message.Message) -> str:
    """Extract plain text from multipart or single-part email payload."""
    body_parts: List[str] = []
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition", ""))
            # Ignore attachments
            if content_type == "text/plain" and "attachment" not in content_disposition:
                payload = part.get_payload(decode=True)
                if payload:
                    body_parts.append(payload.decode("utf-8", errors="replace"))
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            body_parts.append(payload.decode("utf-8", errors="replace"))

    return "\n".join(body_parts).strip()


class MailClient:
    def __init__(self, host: str, port: int, username: str, password: str, dry_run: bool = True):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.dry_run = dry_run
        self.connection: Optional[imaplib.IMAP4_SSL] = None

    def connect(self) -> None:
        """Establish SSL connection and authenticate."""
        self.connection = imaplib.IMAP4_SSL(self.host, self.port)
        self.connection.login(self.username, self.password)

    def disconnect(self) -> None:
        """Close connection cleanly."""
        if self.connection:
            try:
                self.connection.close()
            except Exception:
                pass
            self.connection.logout()

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()

    def fetch_inbox_messages(self, limit: int = 20) -> Generator[EmailMessage, None, None]:
        """Fetch the most recent unread or general messages from INBOX."""
        if not self.connection:
            raise RuntimeError("Client not connected.")

        self.connection.select("INBOX")
        # Search for all messages in INBOX
        status, data = self.connection.search(None, "ALL")
        if status != "OK" or not data[0]:
            return

        message_ids = data[0].split()
        # Grab the newest messages up to `limit`
        target_ids = message_ids[-limit:]

        for msg_id in reversed(target_ids):
            status, fetch_data = self.connection.fetch(msg_id, "(RFC822)")
            if status != "OK":
                continue

            raw_email = fetch_data[0][1]
            msg = email.message_from_bytes(raw_email)

            subject = _clean_header(msg.get("Subject"))
            sender = _clean_header(msg.get("From"))
            body = _extract_text_body(msg)

            yield EmailMessage(
                uid=msg_id.decode("utf-8"),
                sender=sender,
                subject=subject,
                body=body,
            )

    def ensure_folder_exists(self, folder_name: str) -> None:
        """Creates an IMAP folder/mailbox if it does not already exist."""
        if not self.connection:
            raise RuntimeError("Client not connected.")
        # Status check / creation
        status, _ = self.connection.create(f'"{folder_name}"')
        # Return cleanly whether already existed or just created

    def move_message(self, uid: str, target_folder: str) -> None:
        """Copy message to destination folder and flag for deletion in INBOX."""
        if self.dry_run:
            return

        if not self.connection:
            raise RuntimeError("Client not connected.")

        self.ensure_folder_exists(target_folder)
        # IMAP standard move: COPY then mark DELETED
        self.connection.copy(uid, f'"{target_folder}"')
        self.connection.store(uid, "+FLAGS", "\\Deleted")
        self.connection.expunge()

    def delete_message(self, uid: str) -> None:
        """Mark message as deleted and expunge."""
        if self.dry_run:
            return

        if not self.connection:
            raise RuntimeError("Client not connected.")

        self.connection.store(uid, "+FLAGS", "\\Deleted")
        self.connection.expunge()