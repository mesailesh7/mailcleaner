import argparse
import os
import sys
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

from mailcleaner.client import MailClient
from mailcleaner.config import Action
from mailcleaner.engine import EmailClassifier

load_dotenv()
console = Console()

FOLDER_MAP = {
    Action.MOVE_RECEIPTS: "Receipts",
    Action.MOVE_NEWSLETTERS: "Newsletters",
    Action.MOVE_NOTIFICATIONS: "Notifications",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Offline inbox cleaner powered by Laya Local"
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Number of recent inbox messages to analyze"
    )

    parser.add_argument(
        "--execute",
        action="store_true",
        default=False,
        help="Execute real actions (moves & deletes). If omitted, runs in safe dry-run mode."
    )
    return parser.parse_args()


def run() -> None:
    args = parse_args()
    dry_run = not args.execute

    host = os.getenv("IMAP_HOST")
    port = int(os.getenv("IMAP_PORT", "993"))
    user = os.getenv("IMAP_USER")
    password = os.getenv("IMAP_PASS")

    if not all([host, user, password]):
        console.print(
            "[bold red]Configuration error:[/bold red] Missing IMAP credentials in .env file."
        )
        sys.exit(1)

    mode_banner = (
        "[bold yellow]MODE: DRY-RUN (No emails will be moved or deleted)[/bold yellow]"
        if dry_run
        else "[bold red]MODE: LIVE EXECUTION (Emails will be moved/deleted)[/bold red]"
    )
    console.print(mode_banner)
    console.print(f"Connecting to [cyan]{host}[/cyan] as [cyan]{user}[/cyan]...")

    classifier = EmailClassifier()

    with MailClient(host, port, user, password, dry_run=dry_run) as client:
        table = Table(title=f"Scanned Inbox Decisions (Batch size: {args.limit})")
        table.add_column("UID", style="dim", width=6)
        table.add_column("Sender", style="cyan", max_width=25, overflow="ellipsis")
        table.add_column("Subject", style="white", max_width=35, overflow="ellipsis")
        table.add_column("Action", style="bold")
        table.add_column("Junk Prob", justify="right")

        console.print("Fetching and classifying messages...")

        for email_msg in client.fetch_inbox_messages(limit=args.limit):
            decision = classifier.classify_email(
                subject=email_msg.subject,
                sender=email_msg.sender,
                body=email_msg.body,
            )

            action = decision["action"]
            prob = decision["junk_probability"]

            # Style the table row based on the action
            if action == Action.DELETE:
                action_style = "[red]DELETE[/red]"
            elif action == Action.KEEP_INBOX:
                action_style = "[green]KEEP INBOX[/green]"
            else:
                target_folder = FOLDER_MAP.get(action, "Archive")
                action_style = f"[blue]MOVE -> {target_folder}[/blue]"

            table.add_row(
                email_msg.uid,
                email_msg.sender,
                email_msg.subject,
                action_style,
                f"{prob:.1%}",
            )

            # Apply execution if enabled
            if not dry_run:
                if action == Action.DELETE:
                    client.delete_message(email_msg.uid)
                elif action in FOLDER_MAP:
                    client.move_message(email_msg.uid, FOLDER_MAP[action])

        console.print(table)

    if dry_run:
        console.print("\n[dim]To apply these changes for real, pass the flag: [bold]--execute[/bold][/dim]")


if __name__ == "__main__":
    run()
