# MailCleaner

An intelligent, privacy-first inbox cleaner and organizer powered by local AI and configurable rules. MailCleaner works completely offline across Windows, Linux, and macOS.

MailCleaner features an interactive Web UI and a command-line interface with real-time progress bars, encrypted credential management for multiple email providers, and a custom rules engine for routing mail to designated folders.

---

## Features

- **Cross-Platform Compatibility**: Fully supported and tested on Windows, macOS, and Linux.
- **User-Friendly Web UI**: Modern dashboard with live progress bars, account switcher, rule builder, and interactive inbox review.
- **Easy & Secure Email Setup**: Pre-configured templates for Gmail, iCloud, Outlook, Yahoo, Fastmail, and custom IMAP servers. Credentials are encrypted on disk with local machine keys.
- **100% Offline & Private**: Email classification runs entirely locally via Laya. No email contents or metadata are sent to cloud APIs.
- **Progress Visibility**: Real-time progress tracking for model downloading/loading, email fetching, classification, and mailbox actions.
- **Custom Rules & Restrictions**: Create manual routing rules (by sender, domain, subject, or body) that take precedence over AI decisions and route messages to custom folders.
- **Safe Dry-Run by Default**: Preview sorting decisions before committing any mailbox changes.

---

## Installation

### Prerequisites
- Python 3.11 or higher
- [uv](https://github.com/astral-sh/uv) (recommended) or standard `pip`

### Using uv (Recommended)

1. Clone the repository:
```bash
git clone https://github.com/mesailesh7/mailcleaner.git
cd mailcleaner
```

2. Sync dependencies:
```bash
uv sync
```

### Using pip and virtualenv

#### On Linux & macOS:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

#### On Windows (PowerShell):
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e .
```

#### On Windows (Command Prompt):
```cmd
python -m venv .venv
.venv\Scripts\activate.bat
pip install -e .
```

---

## Launching the Application

### 1. Web UI Dashboard

Start the web interface:
```bash
uv run mailcleaner ui
```
Or use the direct shortcut:
```bash
uv run mailcleaner-ui
```

This launches the server at `http://127.0.0.1:8765` and opens your default web browser automatically.

To specify custom host or port:
```bash
uv run mailcleaner ui --host 0.0.0.0 --port 9000 --no-browser
```

### 2. Command-Line Interface (CLI)

Run a safe preview scan (dry-run mode):
```bash
uv run mailcleaner --limit 20
```

Apply real moves and deletions to your mailbox:
```bash
uv run mailcleaner --limit 20 --execute
```

Select a specific saved account profile:
```bash
uv run mailcleaner --account "Work Gmail" --limit 25
```

---

## Email Provider Setup Guides

### Gmail / Google Workspace
1. Go to your **Google Account** settings at `myaccount.google.com`.
2. Select **Security** and confirm **2-Step Verification** is turned on.
3. Search for **App passwords** in the search bar.
4. Create a new app password named `MailCleaner`.
5. In MailCleaner UI, choose **Gmail**, enter your email, and paste the 16-character app password.
- Host: `imap.gmail.com`
- Port: `993` (SSL enabled)

### iCloud Mail
1. Sign in to `appleid.apple.com`.
2. Go to **Sign-In and Security** -> **App-Specific Passwords**.
3. Generate a password named `MailCleaner`.
4. In MailCleaner UI, choose **iCloud Mail**, enter your Apple ID email, and paste the generated password.
- Host: `imap.mail.me.com`
- Port: `993` (SSL enabled)

### Outlook / Hotmail / Office 365
1. Sign in to your Microsoft Account Security settings.
2. Under **Advanced security options**, create an **App password** (if 2FA is active).
3. In MailCleaner UI, choose **Outlook**.
- Host: `outlook.office365.com`
- Port: `993` (SSL enabled)

### Yahoo Mail
1. Open Yahoo Account Security.
2. Select **Generate app password**.
3. In MailCleaner UI, choose **Yahoo Mail**.
- Host: `imap.mail.yahoo.com`
- Port: `993` (SSL enabled)

### Fastmail
1. Go to Fastmail Settings -> **Password & Security** -> **App Passwords**.
2. Generate an app password with Mail access.
3. In MailCleaner UI, choose **Fastmail**.
- Host: `imap.fastmail.com`
- Port: `993` (SSL enabled)

### Custom IMAP Server
Select **Custom IMAP Server** in the UI or set `.env` with your server's host and port.

---

## Rules and Restrictions (Manual Routing)

MailCleaner lets you define custom rules that override AI classification:

1. Open the **Rules & Routing** tab in the Web UI.
2. Configure your condition:
   - **Condition Field**: Sender Address, Subject Line, Sender Domain, or Email Body.
   - **Comparison**: `contains`, `equals`, `starts with`, `ends with`, or `regex`.
   - **Value**: The target phrase, domain, or pattern.
   - **Action**:
     - `Move to Folder` (e.g. `Finance`, `Archive`, `Receipts`, `Work`, or any custom folder)
     - `Keep in Inbox`
     - `Delete / Send to Trash`
3. Click **Save Rule**.
4. Active rules can be enabled, disabled, or deleted at any time.

---

## Security Details

- Account credentials are encrypted on disk using Fernet (AES-128-CBC with HMAC-SHA256 authentication) with keys generated per-machine in `~/.mailcleaner/.key`.
- Key and configuration files are restricted to current user read/write permissions on Unix systems (`0600`).
- Passwords are never logged or exposed in the UI.

---

## Running Tests

Execute the automated test suite with pytest:
```bash
uv run pytest
```
