import email
from email.header import decode_header
import imaplib
import ssl
from typing import Callable, Generator, List, Optional, Tuple
from pydantic import BaseModel

class EmailMessage(BaseModel):
    uid: str
    sender: str
    subject: str
    body: str

def _clean_header(header_value: Optional[str]) -> str:
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
    body_parts: List[str] = []
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition", ""))
            if content_type == "text/plain" and "attachment" not in content_disposition:
                payload = part.get_payload(decode=True)
                if payload:
                    body_parts.append(payload.decode("utf-8", errors="replace"))
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            body_parts.append(payload.decode("utf-8", errors="replace"))
    return "\n".join(body_parts).strip()

def _quote_folder(folder_name: str) -> str:
    sanitized = folder_name.replace('"', '\\"')
    return f'"{sanitized}"'

class MailClient:
    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        use_ssl: bool = True,
        dry_run: bool = True,
    ):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.use_ssl = use_ssl
        self.dry_run = dry_run
        self.connection: Optional[imaplib.IMAP4] = None
        self._cached_folders: Optional[List[str]] = None

    def connect(self) -> None:
        if self.use_ssl:
            ssl_context = ssl.create_default_context()
            self.connection = imaplib.IMAP4_SSL(self.host, self.port, ssl_context=ssl_context)
        else:
            self.connection = imaplib.IMAP4(self.host, self.port)
        self.connection.login(self.username, self.password)

    def disconnect(self) -> None:
        if self.connection:
            try:
                self.connection.close()
            except Exception:
                pass
            try:
                self.connection.logout()
            except Exception:
                pass
            self.connection = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()

    @staticmethod
    def test_credentials(
        host: str,
        port: int,
        username: str,
        password: str,
        use_ssl: bool = True,
    ) -> Tuple[bool, str]:
        try:
            client = MailClient(host, port, username, password, use_ssl=use_ssl, dry_run=True)
            client.connect()
            client.disconnect()
            return True, "Successfully authenticated with mail server."
        except Exception as e:
            return False, str(e)

    def list_folders(self) -> List[str]:
        if not self.connection:
            raise RuntimeError("Client not connected.")
        if self._cached_folders is not None:
            return self._cached_folders
        status, folder_data = self.connection.list()
        folders = []
        if status == "OK" and folder_data:
            for item in folder_data:
                if isinstance(item, bytes):
                    line = item.decode("utf-8", errors="replace")
                    parts = line.split(' "/" ')
                    if len(parts) == 2:
                        folders.append(parts[1].strip('"'))
                    else:
                        folders.append(line.split()[-1].strip('"'))
        self._cached_folders = folders
        return folders

    def ensure_folder_exists(self, folder_name: str) -> None:
        if not self.connection:
            raise RuntimeError("Client not connected.")
        existing = self.list_folders()
        if folder_name in existing or f'"{folder_name}"' in existing:
            return
        try:
            self.connection.create(_quote_folder(folder_name))
            if self._cached_folders is not None:
                self._cached_folders.append(folder_name)
        except Exception:
            pass

    def fetch_inbox_messages(
        self,
        limit: int = 20,
        progress_callback: Optional[Callable[[int, int, Optional[EmailMessage]], None]] = None,
    ) -> Generator[EmailMessage, None, None]:
        if not self.connection:
            raise RuntimeError("Client not connected.")

        self.connection.select("INBOX")
        status, data = self.connection.uid("search", None, "ALL")
        if status != "OK" or not data or not data[0]:
            if progress_callback:
                progress_callback(0, 0, None)
            return

        uids = data[0].split()
        target_uids = uids[-limit:]
        total = len(target_uids)

        for index, uid_bytes in enumerate(reversed(target_uids), start=1):
            uid_str = uid_bytes.decode("utf-8")
            status, fetch_data = self.connection.uid("fetch", uid_bytes, "(RFC822)")
            if status != "OK" or not fetch_data:
                if progress_callback:
                    progress_callback(index, total, None)
                continue

            raw_email = None
            for response_part in fetch_data:
                if isinstance(response_part, tuple) and len(response_part) >= 2:
                    raw_email = response_part[1]
                    break

            if not raw_email or not isinstance(raw_email, bytes):
                if progress_callback:
                    progress_callback(index, total, None)
                continue

            msg = email.message_from_bytes(raw_email)
            subject = _clean_header(msg.get("Subject"))
            sender = _clean_header(msg.get("From"))
            body = _extract_text_body(msg)

            email_obj = EmailMessage(
                uid=uid_str,
                sender=sender,
                subject=subject,
                body=body,
            )

            if progress_callback:
                progress_callback(index, total, email_obj)

            yield email_obj

    def move_message(self, uid: str, target_folder: str) -> None:
        if self.dry_run:
            return
        if not self.connection:
            raise RuntimeError("Client not connected.")

        self.ensure_folder_exists(target_folder)
        quoted_folder = _quote_folder(target_folder)

        move_status, _ = self.connection.uid("MOVE", uid, quoted_folder)
        if move_status != "OK":
            self.connection.uid("COPY", uid, quoted_folder)
            self.connection.uid("STORE", uid, "+FLAGS", "(\\Deleted)")
            self.connection.expunge()

    def delete_message(self, uid: str) -> None:
        if self.dry_run:
            return
        if not self.connection:
            raise RuntimeError("Client not connected.")

        is_gmail = "gmail" in self.host.lower()
        if is_gmail:
            folders = self.list_folders()
            trash_target = "[Gmail]/Trash" if "[Gmail]/Trash" in folders else "[Gmail]/Bin"
            if trash_target in folders:
                self.move_message(uid, trash_target)
                return

        self.connection.uid("STORE", uid, "+FLAGS", "(\\Deleted)")
        self.connection.expunge()