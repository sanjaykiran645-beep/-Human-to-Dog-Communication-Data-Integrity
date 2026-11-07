from tests.conftest import auth_header


def test_user_cannot_read_other_dog(client, user_a, user_b):
    created = client.post(
        "/api/dogs",
        headers=auth_header(user_a["token"]),
        json={"name": "Nala", "breed": "Mix"},
    )
    assert created.status_code == 201
    dog_id = created.json()["id"]
    stolen = client.get(f"/api/dogs/{dog_id}", headers=auth_header(user_b["token"]))
    assert stolen.status_code == 404
    listed = client.get("/api/dogs", headers=auth_header(user_b["token"]))
    assert listed.status_code == 200
    assert listed.json() == []


def test_x_user_id_header_is_ignored(client, user_a, user_b):
    headers = auth_header(user_a["token"])
    headers["X-User-Id"] = user_b["user"]["id"]
    me = client.get("/api/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["id"] == user_a["user"]["id"]


def test_user_cannot_fetch_other_recording_media(client, user_a, user_b, tmp_path):
    from tests.conftest import write_bursts

    wav = write_bursts(tmp_path / "barks.wav")
    with wav.open("rb") as fh:
        res = client.post(
            "/api/recordings/analyze",
            headers=auth_header(user_a["token"]),
            files={"file": ("barks.wav", fh, "audio/wav")},
        )
    assert res.status_code == 200, res.text
    rec_id = res.json()["id"]
    media = client.get(
        f"/api/recordings/{rec_id}/media/processed",
        headers=auth_header(user_b["token"]),
    )
    assert media.status_code == 404
    other = client.get(f"/api/recordings/{rec_id}", headers=auth_header(user_b["token"]))
    assert other.status_code == 404
