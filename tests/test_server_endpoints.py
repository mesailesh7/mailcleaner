import pytest
from starlette.testclient import TestClient
from mailcleaner.server import app

@pytest.fixture
def api_client():
    return TestClient(app)

def test_get_index(api_client):
    response = api_client.get("/")
    assert response.status_code == 200
    assert "MailCleaner" in response.text

def test_get_providers(api_client):
    response = api_client.get("/api/providers")
    assert response.status_code == 200
    data = response.json()
    assert "gmail" in data
    assert "icloud" in data
    assert "outlook" in data
    assert data["gmail"]["host"] == "imap.gmail.com"
    assert data["icloud"]["host"] == "imap.mail.me.com"

def test_rules_crud_endpoints(api_client):
    create_payload = {
        "name": "Integration Test Rule",
        "field": "sender",
        "operator": "contains",
        "value": "alerts@test.org",
        "action": "move",
        "target_folder": "Alerts",
        "enabled": True,
    }
    post_res = api_client.post("/api/rules", json=create_payload)
    assert post_res.status_code == 200
    created = post_res.json()
    assert created["name"] == "Integration Test Rule"
    rule_id = created["id"]

    get_res = api_client.get("/api/rules")
    assert get_res.status_code == 200
    rule_ids = [r["id"] for r in get_res.json()]
    assert rule_id in rule_ids

    del_res = api_client.delete(f"/api/rules/{rule_id}")
    assert del_res.status_code == 200

def test_accounts_crud_endpoints(api_client):
    account_payload = {
        "name": "Test Integration Account",
        "provider": "custom",
        "host": "imap.example.com",
        "port": 993,
        "username": "user@example.com",
        "password": "testpassword123",
        "ssl": True,
        "set_active": False,
    }
    post_res = api_client.post("/api/accounts", json=account_payload)
    assert post_res.status_code == 200
    acc_data = post_res.json()
    acc_id = acc_data["id"]
    assert "encrypted_password" not in acc_data

    list_res = api_client.get("/api/accounts")
    assert list_res.status_code == 200
    accounts = list_res.json()
    assert any(a["id"] == acc_id for a in accounts)

    del_res = api_client.delete(f"/api/accounts/{acc_id}")
    assert del_res.status_code == 200
