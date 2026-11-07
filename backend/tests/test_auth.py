from tests.conftest import auth_header


def test_register_login_me(client):
    email = "auth-flow@example.com"
    r = client.post("/api/auth/register", json={"email": email, "password": "longenough", "name": "Cam"})
    assert r.status_code == 200
    token = r.json()["access_token"]
    me = client.get("/api/auth/me", headers=auth_header(token))
    assert me.status_code == 200
    assert me.json()["email"] == email
    bad = client.post("/api/auth/login", json={"email": email, "password": "wrongpass1"})
    assert bad.status_code == 401
    ok = client.post("/api/auth/login", json={"email": email, "password": "longenough"})
    assert ok.status_code == 200


def test_register_duplicate(client):
    payload = {"email": "dup@example.com", "password": "longenough", "name": "D"}
    assert client.post("/api/auth/register", json=payload).status_code == 200
    assert client.post("/api/auth/register", json=payload).status_code == 409


def test_unauthenticated_dogs(client):
    assert client.get("/api/dogs").status_code == 401


def test_short_password_rejected(client):
    r = client.post("/api/auth/register", json={"email": "s@example.com", "password": "short", "name": "S"})
    assert r.status_code == 422
