from pathlib import Path

from app.services.audio import decoder_status, find_ffmpeg, ffmpeg_encode, write_and_decode
from tests.conftest import auth_header, write_bursts, write_tone


def test_ffmpeg_available():
    st = decoder_status()
    assert st["soundfile_wav"] is True
    assert find_ffmpeg() is not None
    assert st["ffmpeg_available"] is True


def test_health_reports_decoder(client):
    h = client.get("/api/health").json()
    assert "decoder" in h
    assert h["decoder"]["soundfile_wav"] is True


def test_roundtrip_formats(tmp_path: Path, client, user_a):
    wav = write_bursts(tmp_path / "src.wav")
    exe = find_ffmpeg()
    assert exe
    encoded = []
    for fmt, name in [("mp3", "a.mp3"), ("ogg", "a.ogg"), ("flac", "a.flac"), ("webm", "a.webm")]:
        dest = tmp_path / name
        try:
            ffmpeg_encode(wav, dest, fmt)
        except Exception:
            continue
        if dest.exists() and dest.stat().st_size > 64:
            encoded.append(dest)
    assert encoded, "ffmpeg should encode at least one compressed format"
    for f in encoded:
        with f.open("rb") as fh:
            res = client.post(
                "/api/recordings/analyze",
                headers=auth_header(user_a["token"]),
                files={"file": (f.name, fh, "application/octet-stream")},
            )
        assert res.status_code == 200, f"{f.name} {res.text}"
        assert "analysis" in res.json()


def test_magic_not_extension(tmp_path: Path):
    wav = write_tone(tmp_path / "x.wav", 440, 0.5)
    data = wav.read_bytes()
    dest_o = tmp_path / "noext"
    dest_w = tmp_path / "out.wav"
    dest_o.write_bytes(data)
    meta = write_and_decode(data, dest_o, dest_w, "recording")  # no extension
    assert meta["duration"] > 0.2


def test_happy_phrase_generates(client, user_a):
    r = client.post(
        "/api/communicate/generate",
        headers=auth_header(user_a["token"]),
        json={"text": "I am happy."},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "ok"
    assert body["generated"]["is_reference_recording"] is True
    assert body["generated"]["synthetic"] is False
    audio = client.get(
        f"/api/communicate/{body['generated']['id']}/audio",
        headers=auth_header(user_a["token"]),
    )
    assert audio.status_code == 200
    assert audio.content[:4] == b"RIFF"
