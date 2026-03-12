"""
Run tests:  python -m pytest tests/ -v
"""
import sys, os, pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ["DB_PATH"] = ":memory:"

from app.factory import create_app

@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def register(client, username="alice", password="password123"):
    return client.post("/api/auth/register", json={
        "username": username,
        "email": f"{username}@test.com",
        "password": password,
    })


def login(client, username="alice", password="password123"):
    return client.post("/api/auth/login", json={"username": username, "password": password})


def auth_header(token):
    return {"Authorization": f"Bearer {token}"}


# ── Auth tests ────────────────────────────────────────────────────────────────

def test_register(client):
    r = register(client)
    assert r.status_code == 201
    assert "token" in r.get_json()


def test_register_duplicate(client):
    register(client)
    r = register(client)
    assert r.status_code == 409


def test_login(client):
    register(client)
    r = login(client)
    assert r.status_code == 200
    assert "token" in r.get_json()


def test_login_bad_password(client):
    register(client)
    r = client.post("/api/auth/login", json={"username": "alice", "password": "wrong"})
    assert r.status_code == 401


def test_me(client):
    r   = register(client)
    tok = r.get_json()["token"]
    r2  = client.get("/api/auth/me", headers=auth_header(tok))
    assert r2.status_code == 200
    assert r2.get_json()["user"]["username"] == "alice"


# ── Content tests ─────────────────────────────────────────────────────────────

def test_free_content_accessible(client):
    tok = register(client).get_json()["token"]
    r   = client.get("/api/content/free/1", headers=auth_header(tok))
    assert r.status_code == 200


def test_premium_content_blocked_for_free(client):
    tok = register(client).get_json()["token"]
    r   = client.get("/api/content/premium/3", headers=auth_header(tok))
    assert r.status_code == 403
    assert r.get_json()["code"] == "SUBSCRIPTION_REQUIRED"


def test_premium_content_accessible_after_upgrade(client):
    tok = register(client).get_json()["token"]
    client.post("/api/subscriptions/upgrade",
                json={"card_number": "4111111111111111", "months": 1},
                headers=auth_header(tok))
    # Re-login to get fresh token with premium role
    tok2 = login(client).get_json()["token"]
    r = client.get("/api/content/premium/3", headers=auth_header(tok2))
    assert r.status_code == 200


# ── Subscription tests ────────────────────────────────────────────────────────

def test_upgrade(client):
    tok = register(client).get_json()["token"]
    r   = client.post("/api/subscriptions/upgrade",
                      json={"card_number": "4111111111111111", "months": 1},
                      headers=auth_header(tok))
    assert r.status_code == 200
    data = r.get_json()
    assert data["role"] == "premium"
    assert "transaction_ref" in data


def test_upgrade_bad_card(client):
    tok = register(client).get_json()["token"]
    r   = client.post("/api/subscriptions/upgrade",
                      json={"card_number": "123"},
                      headers=auth_header(tok))
    assert r.status_code == 422


def test_no_token(client):
    r = client.get("/api/content/")
    assert r.status_code == 401
