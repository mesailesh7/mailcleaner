import argparse
import os
import sys
from dotenv import load_dotenv
from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table

from mailcleaner.client import MailClient
from mailcleaner.config import DEFAULT_FOLDER_MAP, Action
from mailcleaner.engine import EmailClassifier
from mailcleaner.storage import (
    AccountProfile,
    decrypt_secret,
    get_active_account,
    load_accounts,
    load_rules,
)

load_dotenv()
console = Console()

def resolve_credentials(account_arg: str | None = None) -> tuple[str, int, str, str, bool, dict[str, str]]:
    if account_arg:
        accounts = load_accounts()
        for acc in accounts:
            if acc.name.lower() == account_arg.lower() or acc.id == account_arg:
                pw = decrypt_secret(acc.encrypted_password)
                fmap = acc.folder_map or DEFAULT_FOLDER_MAP
                return acc.host, acc.port, acc.username, pw, acc.ssl, fmap
        console.print(f"[bold red]Error:[/bold red] Account profile '{account_arg}' not found.")
        sys.exit(1)

    active = get_active_account()
    if active and active.encrypted_password:
        pw = decrypt_secret(active.encrypted_password)
        fmap = active.folder_map or DEFAULT_FOLDER_MAP
        return active.host, active.port, active.username, pw, active.ssl, fmap

    host = os.getenv("IMAP_HOST")
    port = int(os.getenv("IMAP_PORT", "993"))
    user = os.getenv("IMAP_USER")
    password = os.getenv("IMAP_PASS")

    if not all([host, user, password]):
        console.print(
            "[bold red]Configuration error:[/bold red] No saved account found and missing IMAP credentials in .env file."
        )
        console.print("Run [bold cyan]mailcleaner ui[/bold cyan] to set up your email account easily in the web interface.")
        sys.exit(1)

    return host, port, user, password, True, DEFAULT_FOLDER_MAP

def run_ui(host: str = "127.0.0.1", port: int = 8765, open_browser: bool = True) -> None:
    from mailcleaner.server import start_server
    console.print(f"[bold green]Starting MailCleaner Web UI on http://{host}:{port}[/bold green]")
    start_server(host=host, port=port, open_browser=open_browser)

def run_cli(limit: int, execute: bool, account: str | None = None) -> None:
    dry_run = not execute
    host, port, user, password, use_ssl, folder_map = resolve_credentials(account)

    mode_banner = (
        "[bold yellow]MODE: DRY-RUN (Safe Preview - No emails moved or deleted)[/bold yellow]"
        if dry_run
        else "[bold red]MODE: LIVE EXECUTION (Emails will be moved/deleted)[/bold red]"
    )
    console.print(mode_banner)
    console.print(f"Connecting to [cyan]{host}:{port}[/cyan] as [cyan]{user}[/cyan]...")

    rules = load_rules()
    if rules:
        console.print(f"Loaded [green]{len(rules)}[/green] custom sorting rules.")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        model_task = progress.add_task("[cyan]Initializing local AI model...", total=1)
        classifier = EmailClassifier()
        progress.update(model_task, advance=1, description="[green]AI model loaded.")

        fetch_task = progress.add_task(f"[cyan]Fetching inbox messages (limit {limit})...", total=limit)
        emails = []

        def on_fetch_progress(curr: int, total: int, msg):
            if msg:
                short_subj = (msg.subject[:30] + "...") if len(msg.subject) > 30 else msg.subject
                progress.update(fetch_task, completed=curr, total=total, description=f"[cyan]Fetched {curr}/{total}: [dim]{short_subj}[/dim]")

        with MailClient(host, port, user, password, use_ssl=use_ssl, dry_run=dry_run) as client:
            for email_msg in client.fetch_inbox_messages(limit=limit, progress_callback=on_fetch_progress):
                emails.append(email_msg)

            progress.update(fetch_task, completed=len(emails), total=len(emails), description=f"[green]Fetched {len(emails)} emails.")

            classify_task = progress.add_task("[cyan]Classifying emails...", total=max(len(emails), 1))
            decisions = []

            for idx, email_msg in enumerate(emails, start=1):
                decision = classifier.classify_email(
                    subject=email_msg.subject,
                    sender=email_msg.sender,
                    body=email_msg.body,
                    custom_rules=rules,
                )
                decisions.append((email_msg, decision))
                progress.update(classify_task, completed=idx, description=f"[cyan]Classifying ({idx}/{len(emails)})...")

            progress.update(classify_task, completed=len(emails), description="[green]Classification complete.")

            if not dry_run and decisions:
                apply_task = progress.add_task("[cyan]Applying actions...", total=len(decisions))
                for idx, (email_msg, decision) in enumerate(decisions, start=1):
                    act = decision["action"]
                    if act == Action.DELETE:
                        client.delete_message(email_msg.uid)
                    elif act == Action.CUSTOM_MOVE and decision.get("target_folder"):
                        client.move_message(email_msg.uid, decision["target_folder"])
                    elif act.value in folder_map:
                        client.move_message(email_msg.uid, folder_map[act.value])
                    progress.update(apply_task, advance=1)

    table = Table(title=f"MailCleaner Decisions ({len(decisions)} messages)")
    table.add_column("UID", style="dim", width=8)
    table.add_column("Sender", style="cyan", max_width=25, overflow="ellipsis")
    table.add_column("Subject", style="white", max_width=35, overflow="ellipsis")
    table.add_column("Rule / Reason", style="magenta", max_width=25, overflow="ellipsis")
    table.add_column("Action", style="bold")
    table.add_column("Junk Prob", justify="right")

    for email_msg, decision in decisions:
        action = decision["action"]
        prob = decision["junk_probability"]
        matched_rule = decision.get("matched_rule")
        reason = f"Rule: {matched_rule}" if matched_rule else f"AI ({decision.get('model_used')})"

        if action == Action.DELETE:
            action_style = "[red]DELETE[/red]"
        elif action == Action.KEEP_INBOX:
            action_style = "[green]KEEP INBOX[/green]"
        elif action == Action.CUSTOM_MOVE:
            dest = decision.get("target_folder") or "Archive"
            action_style = f"[blue]MOVE -> {dest}[/blue]"
        else:
            dest = folder_map.get(action.value, "Archive")
            action_style = f"[blue]MOVE -> {dest}[/blue]"

        table.add_row(
            email_msg.uid,
            email_msg.sender,
            email_msg.subject,
            reason,
            action_style,
            f"{prob:.1%}",
        )

    console.print(table)

    if dry_run:
        console.print("\n[dim]To apply these changes for real, pass: [bold]--execute[/bold][/dim]")
        console.print("[dim]Or run [bold cyan]mailcleaner ui[/bold cyan] for the interactive web dashboard.[/dim]\n")

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Offline inbox cleaner powered by Laya Local and manual rules"
    )
    subparsers = parser.add_subparsers(dest="command")

    ui_parser = subparsers.add_parser("ui", help="Launch the user-friendly web interface")
    ui_parser.add_argument("--host", default="127.0.0.1", help="Web server host")
    ui_parser.add_argument("--port", type=int, default=8765, help="Web server port")
    ui_parser.add_argument("--no-browser", action="store_true", help="Do not open browser automatically")

    parser.add_argument(
        "--ui",
        action="store_true",
        help="Launch the web UI"
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
    parser.add_argument(
        "--account",
        type=str,
        default=None,
        help="Account profile name or ID to use"
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Web server host (when launching UI)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="Web server port (when launching UI)"
    )
    return parser.parse_args()

def run() -> None:
    args = parse_args()
    if args.command == "ui" or args.ui:
        run_ui(host=args.host, port=args.port, open_browser=not getattr(args, "no_browser", False))
    else:
        run_cli(limit=args.limit, execute=args.execute, account=args.account)

if __name__ == "__main__":
    run()
