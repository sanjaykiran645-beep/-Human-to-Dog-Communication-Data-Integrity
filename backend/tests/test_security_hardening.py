"""Hardening regressions: shared-reference immutability, account-deletion erasure, proxy-header trust."""

from pathlib import Path

from tests.conftest import auth_header, write_tone


def _shared_asset(client, token):
    refs = client.get("/api/communicate/references", headers=auth_header(token))
    assert refs.status_code == 200, refs.text
    body = refs.json()
    items = body["assets"] if isinstance(body, dict) and "assets" in body else body.get("references", body)
    shared = [a for a in items if a.get("owner_user_id") in (None, "")]
    return shared[0] if shared else None


def test_shared_reference_cannot_be_relabelled_by_api_user(client, user_a):
    asset = _shared_asset(client, user_a["token"])
    assert asset is not None
    r = client.patch(
        f"/api/communicate/references/{asset['asset_id']}",
        headers=auth_header(user_a["token"]),
        json={"confirmed_category": "HOWL"},
    )
    assert r.status_code == 403, r.text
    again = client.get(f"/api/communicate/references/{asset['asset_id']}", headers=auth_header(user_a["token"]))
    assert again.json()["confirmed_category"] == asset.get("confirmed_category")


def test_account_delete_erases_private_reference_uploads(client, user_a, tmp_path):
    from app.services import reference_library as rl

    wav = write_tone(tmp_path / "mine.wav", 600.0, 1.2, noise=0.02)
    with wav.open("rb") as fh:
        up = client.post(
            "/api/communicate/references/upload",
            headers=auth_header(user_a["token"]),
            files={"file": ("mine.wav", fh, "audio/wav")},
        )
    assert up.status_code == 200, up.text
    asset_id = up.json()["asset_id"]
    proc = Path(rl.get_reference_asset(asset_id, user_a["user"]["id"])["processed_path"])
    assert proc.exists()
    assert client.delete("/api/account", headers=auth_header(user_a["token"])).status_code == 200
    assert not proc.exists()
    assert all(a["asset_id"] != asset_id for a in rl.build_or_load_reference_library()["assets"])


def test_private_reference_invisible_to_other_user(client, user_a, user_b, tmp_path):
    wav = write_tone(tmp_path / "priv.wav", 500.0, 1.0, noise=0.02)
    with wav.open("rb") as fh:
        up = client.post(
            "/api/communicate/references/upload",
            headers=auth_header(user_a["token"]),
            files={"file": ("priv.wav", fh, "audio/wav")},
        )
    aid = up.json()["asset_id"]
    for path in ("", "/audio"):
        r = client.get(f"/api/communicate/references/{aid}{path}", headers=auth_header(user_b["token"]))
        assert r.status_code == 404
    r = client.patch(
        f"/api/communicate/references/{aid}", headers=auth_header(user_b["token"]), json={"confirmed_category": "BARK"}
    )
    assert r.status_code == 404


def test_spoofed_forwarded_for_does_not_reset_rate_limit(client):
    from app import deps

    codes = []
    deps._hits.clear()
    try:
        for i in range(deps.RATE_LIMIT_AUTH + 5):
            r = client.post(
                "/api/auth/login",
                headers={"X-Forwarded-For": f"10.0.0.{i}"},
                json={"email": "nobody@example.com", "password": "wrongpassword1"},
            )
            codes.append(r.status_code)
    finally:
        deps._hits.clear()  # do not starve other tests that share the client IP
    assert 429 in codes


def test_unauthenticated_requests_rejected(client):
    for path in ("/api/dogs", "/api/recordings", "/api/communicate", "/api/communicate/references", "/api/analytics/summary"):
        assert client.get(path).status_code == 401, path
