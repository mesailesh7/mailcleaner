import asyncio
import json
import os
import sys
import webbrowser
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from mailcleaner.client import MailClient
from mailcleaner.config import (
    DEFAULT_FOLDER_MAP,
    PROVIDER_PRESETS,
    Action,
)
from mailcleaner.engine import EmailClassifier
from mailcleaner.storage import (
    AccountProfile,
    Rule,
    decrypt_secret,
    delete_account,
    delete_rule,
    get_active_account,
    load_accounts,
    load_rules,
    save_rules,
    set_active_account,
    upsert_account,
    upsert_rule,
)

app = FastAPI(title="MailCleaner")

WEB_DIR = Path(__file__).parent / "web"
INDEX_FILE = WEB_DIR / "index.html"

class AccountCreateRequest(BaseModel):
    id: Optional[str] = None
    name: str
    provider: str
    host: str
    port: int = 993
    username: str
    password: str
    ssl: bool = True
    folder_map: Optional[Dict[str, str]] = None
    set_active: bool = True

class TestConnectionRequest(BaseModel):
    host: str
    port: int = 993
    username: str
    password: str
    ssl: bool = True

class RuleRequest(BaseModel):
    id: Optional[str] = None
    name: str
    enabled: bool = True
    field: str
    operator: str
    value: str
    action: str
    target_folder: Optional[str] = None

class ScanRequest(BaseModel):
    limit: int = 15
    execute: bool = False
    account_id: Optional[str] = None

class BatchExecuteItem(BaseModel):
    uid: str
    action: str
    target_folder: Optional[str] = None

class BatchExecuteRequest(BaseModel):
    account_id: Optional[str] = None
    items: List[BatchExecuteItem]

def _resolve_account(account_id: Optional[str] = None) -> Optional[AccountProfile]:
    if account_id:
        accounts = load_accounts()
        for acc in accounts:
            if acc.id == account_id:
                return acc
    active = get_active_account()
    if active:
        return active
    env_host = os.getenv("IMAP_HOST")
    env_user = os.getenv("IMAP_USER")
    env_pass = os.getenv("IMAP_PASS")
    env_port = int(os.getenv("IMAP_PORT", "993"))
    if env_host and env_user and env_pass:
        return AccountProfile(
            name="Default (.env)",
            provider="custom",
            host=env_host,
            port=env_port,
            ssl=True,
            username=env_user,
            encrypted_password="",
            is_active=True,
        )
    return None

def _get_account_password(account: AccountProfile) -> str:
    if account.encrypted_password:
        return decrypt_secret(account.encrypted_password)
    env_pass = os.getenv("IMAP_PASS")
    if env_pass:
        return env_pass
    return ""

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    if not INDEX_FILE.exists():
        raise HTTPException(status_code=404, detail="Web UI frontend file not found.")
    return HTMLResponse(content=INDEX_FILE.read_text(encoding="utf-8"))

@app.get("/api/providers")
async def get_providers():
    return PROVIDER_PRESETS

@app.get("/api/accounts")
async def list_accounts():
    accounts = load_accounts()
    result = []
    for acc in accounts:
        item = acc.model_dump()
        item["has_password"] = bool(acc.encrypted_password)
        item.pop("encrypted_password", None)
        result.append(item)
    return result

@app.post("/api/accounts")
async def create_or_update_account(req: AccountCreateRequest):
    if not req.password and req.id:
        existing_accounts = load_accounts()
        for existing in existing_accounts:
            if existing.id == req.id:
                raw_password = decrypt_secret(existing.encrypted_password)
                break
        else:
            raise HTTPException(status_code=400, detail="Password is required for new accounts.")
    else:
        raw_password = req.password

    profile = upsert_account(
        name=req.name,
        provider=req.provider,
        host=req.host,
        port=req.port,
        username=req.username,
        password=raw_password,
        ssl=req.ssl,
        account_id=req.id,
        folder_map=req.folder_map,
        set_active=req.set_active,
    )
    result = profile.model_dump()
    result.pop("encrypted_password", None)
    return result

@app.delete("/api/accounts/{account_id}")
async def remove_account(account_id: str):
    success = delete_account(account_id)
    if not success:
        raise HTTPException(status_code=404, detail="Account not found.")
    return {"success": True}

@app.post("/api/accounts/{account_id}/activate")
async def activate_account(account_id: str):
    success = set_active_account(account_id)
    if not success:
        raise HTTPException(status_code=404, detail="Account not found.")
    return {"success": True}

@app.post("/api/accounts/test")
async def test_connection(req: TestConnectionRequest):
    success, message = MailClient.test_credentials(
        host=req.host,
        port=req.port,
        username=req.username,
        password=req.password,
        use_ssl=req.ssl,
    )
    return {"success": success, "message": message}

@app.get("/api/rules")
async def get_rules():
    rules = load_rules()
    return [r.model_dump() for r in rules]

@app.post("/api/rules")
async def create_or_update_rule(req: RuleRequest):
    rule = upsert_rule(req.model_dump())
    return rule.model_dump()

@app.delete("/api/rules/{rule_id}")
async def remove_rule(rule_id: str):
    success = delete_rule(rule_id)
    if not success:
        raise HTTPException(status_code=404, detail="Rule not found.")
    return {"success": True}

@app.get("/api/folders")
async def get_folders(account_id: Optional[str] = None):
    account = _resolve_account(account_id)
    if not account:
        raise HTTPException(status_code=400, detail="No email account configured.")
    password = _get_account_password(account)
    try:
        with MailClient(account.host, account.port, account.username, password, use_ssl=account.ssl) as client:
            folders = client.list_folders()
            return {"folders": folders}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/scan")
async def scan_inbox(req: ScanRequest):
    account = _resolve_account(req.account_id)
    if not account:
        raise HTTPException(status_code=400, detail="No email account configured.")
    password = _get_account_password(account)
    if not password:
        raise HTTPException(status_code=400, detail="Account password missing.")

    rules = load_rules()
    folder_map = account.folder_map if account.folder_map else DEFAULT_FOLDER_MAP

    async def event_generator():
        yield f"data: {json.dumps({'type': 'status', 'step': 'init', 'message': 'Initializing email client...'})}\n\n"
        await asyncio.sleep(0.05)

        try:
            client = MailClient(
                account.host,
                account.port,
                account.username,
                password,
                use_ssl=account.ssl,
                dry_run=not req.execute,
            )
            client.connect()
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': f'Failed to connect to {account.host}: {str(e)}'})}\n\n"
            return

        yield f"data: {json.dumps({'type': 'status', 'step': 'model', 'message': 'Loading AI decision engine...'})}\n\n"
        await asyncio.sleep(0.05)

        try:
            classifier = EmailClassifier()
        except Exception as e:
            client.disconnect()
            yield f"data: {json.dumps({'type': 'error', 'message': f'Failed to load model: {str(e)}'})}\n\n"
            return

        yield f"data: {json.dumps({'type': 'status', 'step': 'fetching', 'message': f'Scanning latest {req.limit} inbox emails...'})}\n\n"
        await asyncio.sleep(0.05)

        try:
            messages = []
            for msg in client.fetch_inbox_messages(limit=req.limit):
                messages.append(msg)
                yield f"data: {json.dumps({'type': 'progress', 'step': 'fetch', 'current': len(messages), 'total': req.limit, 'sender': msg.sender, 'subject': msg.subject})}\n\n"
                await asyncio.sleep(0.02)

            total_found = len(messages)
            yield f"data: {json.dumps({'type': 'status', 'step': 'classifying', 'message': f'Classifying {total_found} emails with rules and AI...', 'total': total_found})}\n\n"
            await asyncio.sleep(0.05)

            results = []
            for idx, msg in enumerate(messages, start=1):
                decision = classifier.classify_email(
                    subject=msg.subject,
                    sender=msg.sender,
                    body=msg.body,
                    custom_rules=rules,
                )

                action = decision["action"]
                prob = decision["junk_probability"]
                target_folder = None

                if action == Action.DELETE:
                    action_label = "DELETE"
                elif action == Action.KEEP_INBOX:
                    action_label = "KEEP"
                elif action == Action.CUSTOM_MOVE:
                    action_label = "MOVE"
                    target_folder = decision.get("target_folder") or "Archive"
                else:
                    action_label = "MOVE"
                    target_folder = folder_map.get(action.value, "Archive")

                email_record = {
                    "uid": msg.uid,
                    "sender": msg.sender,
                    "subject": msg.subject,
                    "action": action_label,
                    "raw_action": action.value,
                    "target_folder": target_folder,
                    "junk_probability": round(prob, 4),
                    "model_used": decision.get("model_used"),
                    "matched_rule": decision.get("matched_rule"),
                }

                if req.execute:
                    if action == Action.DELETE:
                        client.delete_message(msg.uid)
                        email_record["executed"] = True
                    elif action_label == "MOVE" and target_folder:
                        client.move_message(msg.uid, target_folder)
                        email_record["executed"] = True
                    else:
                        email_record["executed"] = False
                else:
                    email_record["executed"] = False

                results.append(email_record)
                yield f"data: {json.dumps({'type': 'email_result', 'current': idx, 'total': total_found, 'data': email_record})}\n\n"
                await asyncio.sleep(0.02)

            client.disconnect()
            yield f"data: {json.dumps({'type': 'done', 'total': total_found, 'execute': req.execute})}\n\n"

        except Exception as e:
            try:
                client.disconnect()
            except Exception:
                pass
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.post("/api/execute-batch")
async def execute_batch(req: BatchExecuteRequest):
    account = _resolve_account(req.account_id)
    if not account:
        raise HTTPException(status_code=400, detail="No email account configured.")
    password = _get_account_password(account)
    if not password:
        raise HTTPException(status_code=400, detail="Account password missing.")

    folder_map = account.folder_map if account.folder_map else DEFAULT_FOLDER_MAP
    executed_count = 0
    errors = []

    try:
        with MailClient(account.host, account.port, account.username, password, use_ssl=account.ssl, dry_run=False) as client:
            for item in req.items:
                try:
                    if item.action == "DELETE":
                        client.delete_message(item.uid)
                        executed_count += 1
                    elif item.action == "MOVE":
                        folder = item.target_folder or "Archive"
                        client.move_message(item.uid, folder)
                        executed_count += 1
                except Exception as err:
                    errors.append(f"UID {item.uid}: {str(err)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "success": True,
        "executed_count": executed_count,
        "errors": errors,
    }

def start_server(host: str = "127.0.0.1", port: int = 8765, open_browser: bool = True):
    import uvicorn
    if open_browser:
        def _open():
            webbrowser.open(f"http://{host}:{port}")
        loop = asyncio.get_event_loop() if asyncio.events._get_running_loop() else None
        if loop and loop.is_running():
            loop.call_later(1.0, _open)
        else:
            import threading
            timer = threading.Timer(1.0, _open)
            timer.daemon = True
            timer.start()
    uvicorn.run(app, host=host, port=port, log_level="info")
