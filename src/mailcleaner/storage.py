import json
import os
import re
import stat
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional
from cryptography.fernet import Fernet
from pydantic import BaseModel, Field

from mailcleaner.config import (
    APP_DIR,
    CONFIG_FILE,
    DEFAULT_FOLDER_MAP,
    KEY_FILE,
    PROVIDER_PRESETS,
    RULES_FILE,
    Action,
)

class Rule(BaseModel):
    id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    enabled: bool = True
    field: str = "sender"
    operator: str = "contains"
    value: str
    action: str = "receipts"
    target_folder: Optional[str] = None

class AccountProfile(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    provider: str = "custom"
    host: str
    port: int = 993
    ssl: bool = True
    username: str
    encrypted_password: str
    folder_map: Dict[str, str] = Field(default_factory=lambda: dict(DEFAULT_FOLDER_MAP))
    is_active: bool = False

def _ensure_app_dir() -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    if os.name != "nt":
        try:
            os.chmod(APP_DIR, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
        except OSError:
            pass

def _get_or_create_cipher() -> Fernet:
    _ensure_app_dir()
    if not KEY_FILE.exists():
        key = Fernet.generate_key()
        KEY_FILE.write_bytes(key)
        if os.name != "nt":
            try:
                os.chmod(KEY_FILE, stat.S_IRUSR | stat.S_IWUSR)
            except OSError:
                pass
    else:
        key = KEY_FILE.read_bytes()
    return Fernet(key)

def encrypt_secret(secret: str) -> str:
    cipher = _get_or_create_cipher()
    return cipher.encrypt(secret.encode("utf-8")).decode("utf-8")

def decrypt_secret(encrypted_secret: str) -> str:
    cipher = _get_or_create_cipher()
    return cipher.decrypt(encrypted_secret.encode("utf-8")).decode("utf-8")

def load_accounts() -> List[AccountProfile]:
    _ensure_app_dir()
    if not CONFIG_FILE.exists():
        return []
    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        accounts_data = data.get("accounts", [])
        return [AccountProfile(**acc) for acc in accounts_data]
    except Exception:
        return []

def save_accounts(accounts: List[AccountProfile]) -> None:
    _ensure_app_dir()
    data = {"accounts": [acc.model_dump() for acc in accounts]}
    CONFIG_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    if os.name != "nt":
        try:
            os.chmod(CONFIG_FILE, stat.S_IRUSR | stat.S_IWUSR)
        except OSError:
            pass

def get_active_account() -> Optional[AccountProfile]:
    accounts = load_accounts()
    for acc in accounts:
        if acc.is_active:
            return acc
    if accounts:
        return accounts[0]
    return None

def set_active_account(account_id: str) -> bool:
    accounts = load_accounts()
    found = False
    for acc in accounts:
        if acc.id == account_id:
            acc.is_active = True
            found = True
        else:
            acc.is_active = False
    if found:
        save_accounts(accounts)
    return found

def upsert_account(
    name: str,
    provider: str,
    host: str,
    port: int,
    username: str,
    password: str,
    ssl: bool = True,
    account_id: Optional[str] = None,
    folder_map: Optional[Dict[str, str]] = None,
    set_active: bool = True,
) -> AccountProfile:
    accounts = load_accounts()
    encrypted_pw = encrypt_secret(password)
    assigned_folder_map = folder_map if folder_map is not None else dict(DEFAULT_FOLDER_MAP)

    target_profile: Optional[AccountProfile] = None
    if account_id:
        for acc in accounts:
            if acc.id == account_id:
                acc.name = name
                acc.provider = provider
                acc.host = host
                acc.port = port
                acc.ssl = ssl
                acc.username = username
                acc.encrypted_password = encrypted_pw
                acc.folder_map = assigned_folder_map
                target_profile = acc
                break

    if target_profile is None:
        target_profile = AccountProfile(
            name=name,
            provider=provider,
            host=host,
            port=port,
            ssl=ssl,
            username=username,
            encrypted_password=encrypted_pw,
            folder_map=assigned_folder_map,
            is_active=set_active or len(accounts) == 0,
        )
        accounts.append(target_profile)

    if set_active:
        for acc in accounts:
            acc.is_active = (acc.id == target_profile.id)

    save_accounts(accounts)
    return target_profile

def delete_account(account_id: str) -> bool:
    accounts = load_accounts()
    initial_len = len(accounts)
    accounts = [acc for acc in accounts if acc.id != account_id]
    if len(accounts) < initial_len:
        if accounts and not any(acc.is_active for acc in accounts):
            accounts[0].is_active = True
        save_accounts(accounts)
        return True
    return False

def load_rules() -> List[Rule]:
    _ensure_app_dir()
    if not RULES_FILE.exists():
        default_rules = [
            Rule(
                name="Security & 2FA Notifications",
                field="subject",
                operator="contains",
                value="verification code",
                action="notifications",
                target_folder="Notifications",
            ),
            Rule(
                name="GitHub Activity",
                field="sender",
                operator="contains",
                value="notifications@github.com",
                action="notifications",
                target_folder="Notifications",
            ),
            Rule(
                name="Invoices & Receipts",
                field="subject",
                operator="contains",
                value="receipt",
                action="receipts",
                target_folder="Receipts",
            ),
        ]
        save_rules(default_rules)
        return default_rules
    try:
        data = json.loads(RULES_FILE.read_text(encoding="utf-8"))
        return [Rule(**item) for item in data.get("rules", [])]
    except Exception:
        return []

def save_rules(rules: List[Rule]) -> None:
    _ensure_app_dir()
    data = {"rules": [rule.model_dump() for rule in rules]}
    RULES_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")

def upsert_rule(rule_data: Dict[str, Any]) -> Rule:
    rules = load_rules()
    rule_id = rule_data.get("id")
    rule_obj: Optional[Rule] = None

    if rule_id:
        for r in rules:
            if r.id == rule_id:
                for key, val in rule_data.items():
                    setattr(r, key, val)
                rule_obj = r
                break
    else:
        rule_data.pop("id", None)

    if rule_obj is None:
        rule_obj = Rule(**rule_data)
        if not rule_obj.id:
            rule_obj.id = str(uuid.uuid4())
        rules.append(rule_obj)

    save_rules(rules)
    return rule_obj

def delete_rule(rule_id: str) -> bool:
    rules = load_rules()
    initial_len = len(rules)
    rules = [r for r in rules if r.id != rule_id]
    if len(rules) < initial_len:
        save_rules(rules)
        return True
    return False

def match_rule_condition(field_value: str, operator: str, expected_value: str) -> bool:
    fv = field_value.lower()
    ev = expected_value.lower()
    if operator == "contains":
        return ev in fv
    elif operator == "equals":
        return fv.strip() == ev.strip()
    elif operator == "starts_with":
        return fv.startswith(ev)
    elif operator == "ends_with":
        return fv.endswith(ev)
    elif operator == "regex":
        try:
            return bool(re.search(expected_value, field_value, re.IGNORECASE))
        except re.error:
            return False
    return False

def evaluate_manual_rules(
    rules: List[Rule],
    sender: str,
    subject: str,
    body: str,
) -> Optional[Dict[str, Any]]:
    for rule in rules:
        if not rule.enabled:
            continue

        target_text = ""
        if rule.field == "sender":
            target_text = sender
        elif rule.field == "subject":
            target_text = subject
        elif rule.field == "body":
            target_text = body[:4000]
        elif rule.field == "domain":
            match = re.search(r"@([\w.-]+)", sender)
            target_text = match.group(1) if match else sender

        if match_rule_condition(target_text, rule.operator, rule.value):
            action_str = rule.action
            target_folder = rule.target_folder
            if action_str == "delete":
                resolved_action = Action.DELETE
            elif action_str == "keep":
                resolved_action = Action.KEEP_INBOX
            elif action_str == "receipts":
                resolved_action = Action.MOVE_RECEIPTS
            elif action_str == "newsletters":
                resolved_action = Action.MOVE_NEWSLETTERS
            elif action_str == "notifications":
                resolved_action = Action.MOVE_NOTIFICATIONS
            elif action_str == "move":
                resolved_action = Action.CUSTOM_MOVE
            else:
                resolved_action = Action.CUSTOM_MOVE

            return {
                "action": resolved_action,
                "rule_name": rule.name,
                "target_folder": target_folder,
                "source": "manual_rule",
            }

    return None
