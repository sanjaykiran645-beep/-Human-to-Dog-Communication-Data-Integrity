from pathlib import Path

from tests.conftest import auth_header, write_bursts


def test_generate_requires_auth(client):
    r = client.post("/api/communicate/generate", json={"text": "come here"})
    assert r.status_code == 401


def test_intent_endpoint_deterministic_pipeline(client, user_a):
    r = client.post(
        "/api/communicate/intent",
        headers=auth_header(user_a["token"]),
        json={"text": "  Come   Here!  "},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["original_input"] == "  Come   Here!  "
    assert body["normalized_input"] == "come here!"
    assert body["detected_intent"] == "come"
    assert body["selected_synthesis_profile"] == "bark"
    assert body["reference_category"] == "BARK"
    assert len(body["reference_candidates"]) >= 1
    assert body["validation"]["valid"] is True
    assert body["synthesis_parameters"]["vocalization"] == "bark"
    assert body["synthesis_parameters"]["sr"] == 22050


def test_intent_invalid_and_empty_input(client, user_a):
    r_empty = client.post(
        "/api/communicate/intent",
        headers=auth_header(user_a["token"]),
        json={"text": "   "},
    )
    assert r_empty.status_code == 200
    assert r_empty.json()["validation"]["valid"] is False
    assert r_empty.json()["intent"] == "unsupported"

    gen_empty = client.post(
        "/api/communicate/generate",
        headers=auth_header(user_a["token"]),
        json={"text": "   "},
    )
    assert gen_empty.status_code == 400


def test_generate_reference_direct_and_media(client, user_a):
    r = client.post(
        "/api/communicate/generate",
        headers=auth_header(user_a["token"]),
        json={"text": "come here"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "ok"
    gen = body["generated"]
    assert gen["generation_method"] == "reference_direct"
    assert gen["is_reference_recording"] is True
    assert gen["is_modified_recording"] is False
    assert gen["synthetic"] is False
    assert gen["output_classification"] == "Original Reference Audio (Retrieval)"
    assert gen["primary_reference_asset"] is not None
    assert gen["acoustic_comparison"]["spectral_envelope_similarity"] >= 0.98
    assert gen["acoustic_comparison"]["unnatural_crackle_or_transient_detected"] is False
    assert gen["validation"]["valid"] is True
    assert gen["validation"]["non_silent"] is True
    assert gen["validation"]["finite_samples"] is True
    assert len(gen["validation"]["sha256"]) == 64

    gen_id = gen["id"]
    audio = client.get(f"/api/communicate/{gen_id}/audio", headers=auth_header(user_a["token"]))
    assert audio.status_code == 200
    assert audio.headers["content-type"].startswith("audio/")
    assert audio.content[:4] == b"RIFF"

    wave = client.get(f"/api/communicate/{gen_id}/media/waveform", headers=auth_header(user_a["token"]))
    assert wave.status_code == 200
    assert wave.headers["content-type"] == "image/png"

    spec = client.get(f"/api/communicate/{gen_id}/media/spectrogram", headers=auth_header(user_a["token"]))
    assert spec.status_code == 200
    assert spec.headers["content-type"] == "image/png"

    spec_data = client.get(f"/api/communicate/{gen_id}/spectrogram-data", headers=auth_header(user_a["token"]))
    assert spec_data.status_code == 200
    sd = spec_data.json()
    assert sd["valid"] is True
    assert sd["stft_config"]["window"] == "hann"
    assert sd["signal_metrics"]["is_silent"] is False


def test_generate_reference_variation_and_experimental_dsp(client, user_a):
    # Method B: Controlled reference variation
    r_var = client.post(
        "/api/communicate/generate",
        headers=auth_header(user_a["token"]),
        json={
            "text": "easy settle down",
            "vocalization_target": "whimper",
            "generation_method": "reference_variation",
            "pitch_shift_semitones": 0.5,
            "time_stretch_rate": 0.95,
        },
    )
    assert r_var.status_code == 200, r_var.text
    g_var = r_var.json()["generated"]
    assert g_var["generation_method"] == "reference_variation"
    assert g_var["is_modified_recording"] is True
    assert g_var["is_reference_recording"] is False
    assert g_var["synthetic"] is False
    assert g_var["output_classification"] == "Transformed Reference Audio (Modified Recording)"
    assert g_var["acoustic_comparison"]["spectral_envelope_similarity"] >= 0.90

    # Method C: Generative model assessment & transparent fallback
    r_mod = client.post(
        "/api/communicate/generate",
        headers=auth_header(user_a["token"]),
        json={
            "text": "howl",
            "vocalization_target": "howl",
            "generation_method": "generative_model",
        },
    )
    assert r_mod.status_code == 200, r_mod.text
    g_mod = r_mod.json()["generated"]
    assert g_mod["generation_method"] == "reference_variation"
    assert any("METHOD C UNAVAILABLE" in w for w in g_mod["generation_warnings"])

    # Method D: Experimental DSP fallback
    r_dsp = client.post(
        "/api/communicate/generate",
        headers=auth_header(user_a["token"]),
        json={
            "text": "come here",
            "vocalization_target": "bark",
            "generation_method": "experimental_dsp",
        },
    )
    assert r_dsp.status_code == 200, r_dsp.text
    g_dsp = r_dsp.json()["generated"]
    assert g_dsp["generation_method"] == "experimental_dsp"
    assert g_dsp["synthetic"] is True
    assert g_dsp["output_classification"] == "Experimental DSP Output (Synthetic)"


def test_reference_library_endpoints_and_label_review(client, user_a, tmp_path: Path):
    r_lib = client.get("/api/communicate/references", headers=auth_header(user_a["token"]))
    assert r_lib.status_code == 200
    lib = r_lib.json()
    assert lib["total_accepted_canine_references"] >= 50
    assert len(lib["assets"]) >= 50
    first_asset = lib["assets"][0]
    asset_id = first_asset["asset_id"]

    # Audio & spectrogram for reference asset
    r_aud = client.get(f"/api/communicate/references/{asset_id}/audio", headers=auth_header(user_a["token"]))
    assert r_aud.status_code == 200
    assert r_aud.content[:4] == b"RIFF"

    r_spec = client.get(f"/api/communicate/references/{asset_id}/spectrogram-data", headers=auth_header(user_a["token"]))
    assert r_spec.status_code == 200
    assert r_spec.json()["valid"] is True

    # Shared library assets are read-only for API users (relabelling would affect everyone).
    r_patch = client.patch(
        f"/api/communicate/references/{asset_id}",
        headers=auth_header(user_a["token"]),
        json={"confirmed_category": "BARK", "notes": "must be rejected"},
    )
    assert r_patch.status_code == 403

    # A user CAN review the label of their own private upload.
    from tests.conftest import write_tone

    wav = write_tone(tmp_path / "own.wav", 700.0, 1.0, noise=0.02)
    with wav.open("rb") as fh:
        up = client.post(
            "/api/communicate/references/upload",
            headers=auth_header(user_a["token"]),
            files={"file": ("own.wav", fh, "audio/wav")},
        )
    assert up.status_code == 200, up.text
    own_id = up.json()["asset_id"]
    r_own = client.patch(
        f"/api/communicate/references/{own_id}",
        headers=auth_header(user_a["token"]),
        json={"confirmed_category": "BARK", "notes": "Verified in automated test"},
    )
    assert r_own.status_code == 200
    assert r_own.json()["confirmed_category"] == "BARK"
    assert r_own.json()["label_verification"] == "verified_by_named_reviewer"


def test_generated_audio_idor(client, user_a, user_b):
    r = client.post(
        "/api/communicate/generate",
        headers=auth_header(user_a["token"]),
        json={"text": "come here"},
    )
    gen_id = r.json()["generated"]["id"]
    assert client.get(f"/api/communicate/{gen_id}/audio", headers=auth_header(user_b["token"])).status_code == 404
    assert client.get(f"/api/communicate/{gen_id}/spectrogram-data", headers=auth_header(user_b["token"])).status_code == 404
    assert client.get(f"/api/communicate/{gen_id}/responses", headers=auth_header(user_b["token"])).status_code == 404


def test_ambiguous_needs_clarification(client, user_a):
    r = client.post(
        "/api/communicate/generate",
        headers=auth_header(user_a["token"]),
        json={"text": "come here and stay and play with the ball"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "needs_clarification"
    assert r.json()["generated"] is None
    assert "come" in r.json()["intent"]["candidates"]


def test_generate_custom_synth_params_and_idempotency(client, user_a):
    idem_key = "test-idem-key-001"
    payload = {
        "text": "let's play",
        "vocalization_target": "yip",
        "generation_method": "reference_variation",
        "intensity": 0.75,
        "duration_sec": 0.4,
        "pitch_hz": 880,
        "idempotency_key": idem_key,
    }
    r1 = client.post("/api/communicate/generate", headers=auth_header(user_a["token"]), json=payload)
    assert r1.status_code == 200, r1.text
    b1 = r1.json()
    assert b1["status"] == "ok"
    assert b1["generated"]["vocalization_target"] == "yip"
    assert abs(b1["generated"]["params"]["duration"] - 0.4) < 0.08

    # Retrying with the same idempotency_key must return the exact same record without duplicating
    r2 = client.post("/api/communicate/generate", headers=auth_header(user_a["token"]), json=payload)
    assert r2.status_code == 200
    b2 = r2.json()
    assert b2.get("idempotent_retry") is True
    assert b2["generated"]["id"] == b1["generated"]["id"]

    # Record listening feedback
    gen_id = b1["generated"]["id"]
    r_fb = client.post(
        f"/api/communicate/{gen_id}/feedback",
        headers=auth_header(user_a["token"]),
        json={"rating": 5, "sounds_natural": True, "notes": "Clean real dog yip"},
    )
    assert r_fb.status_code == 200
    assert r_fb.json()["user_feedback"]["rating"] == 5


def test_communicate_response_recording_persistence_and_retry(client, user_a, user_b, tmp_path: Path):
    gen_res = client.post(
        "/api/communicate/generate",
        headers=auth_header(user_a["token"]),
        json={"text": "good dog"},
    )
    assert gen_res.status_code == 200
    gen_id = gen_res.json()["generated"]["id"]

    wav = write_bursts(tmp_path / "dog_resp.wav")
    with wav.open("rb") as fh:
        resp1 = client.post(
            f"/api/communicate/{gen_id}/response",
            headers=auth_header(user_a["token"]),
            files={"file": ("dog_resp.wav", fh, "audio/wav")},
        )
    assert resp1.status_code == 200, resp1.text
    d1 = resp1.json()
    assert d1["generated_id"] == gen_id
    assert d1["recording"]["source"] == "dog_response"
    assert d1["recording"]["analysis"]["vocalization"]
    assert "not proof" in d1["interpretation_warning"]

    # Retry with the identical audio payload must be idempotent (no duplicate row)
    with wav.open("rb") as fh:
        resp2 = client.post(
            f"/api/communicate/{gen_id}/response",
            headers=auth_header(user_a["token"]),
            files={"file": ("dog_resp.wav", fh, "audio/wav")},
        )
    assert resp2.status_code == 200
    d2 = resp2.json()
    assert d2.get("idempotent_retry") is True
    assert d2["id"] == d1["id"]

    # Verify list_generated_responses returns exactly 1 persisted response
    listed = client.get(f"/api/communicate/{gen_id}/responses", headers=auth_header(user_a["token"]))
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert listed.json()[0]["id"] == d1["id"]

    # Cross-user denial on response submission
    with wav.open("rb") as fh:
        denied = client.post(
            f"/api/communicate/{gen_id}/response",
            headers=auth_header(user_b["token"]),
            files={"file": ("dog_resp.wav", fh, "audio/wav")},
        )
    assert denied.status_code == 404


def test_all_11_categories_method_a_exact_match_and_valid_wav(client, user_a):
    categories = [
        "BARK",
        "GROWL",
        "HOWL",
        "WHINE",
        "YIP",
        "YELP",
        "WHIMPER",
        "CRY",
        "GRUNT",
        "GROAN",
        "PANT",
    ]
    for cat in categories:
        res = client.post(
            "/api/communicate/generate",
            headers=auth_header(user_a["token"]),
            json={
                "text": f"test {cat.lower()}",
                "vocalization_target": cat.lower(),
                "generation_method": "reference_direct",
            },
        )
        assert res.status_code == 200, f"Failed for {cat}: {res.text}"
        gen = res.json()["generated"]
        assert gen["requested_category"] == cat
        assert gen["generation_method"] == "reference_direct"
        assert gen["is_reference_recording"] is True
        assert gen["primary_reference_asset"]["effective_category"] == cat
        assert gen["primary_reference_asset"]["match_tier"] == "exact_category"
        assert gen["validation"]["valid"] is True
        assert gen["validation"]["non_silent"] is True


def test_user_uploaded_reference_ownership_isolation(client, user_a, user_b, tmp_path: Path):
    wav = write_bursts(tmp_path / "private_user_a_dog.wav")
    with wav.open("rb") as fh:
        up = client.post(
            "/api/communicate/references/upload",
            headers=auth_header(user_a["token"]),
            files={"file": ("private_user_a_dog.wav", fh, "audio/wav")},
            data={"confirmed_category": "BARK", "source_dog_id": "dog_private_a"},
        )
    assert up.status_code == 200, up.text
    asset_id = up.json()["asset_id"]
    assert up.json()["owner_user_id"] == user_a["user"]["id"]

    # User A can access their uploaded reference recording
    assert client.get(f"/api/communicate/references/{asset_id}", headers=auth_header(user_a["token"])).status_code == 200
    assert client.get(f"/api/communicate/references/{asset_id}/audio", headers=auth_header(user_a["token"])).status_code == 200

    # User B MUST NOT see User A's uploaded reference recording in list, detail, audio, patch, or generate
    lib_b = client.get("/api/communicate/references", headers=auth_header(user_b["token"])).json()
    b_ids = {a["asset_id"] for a in lib_b["assets"]}
    assert asset_id not in b_ids
    assert client.get(f"/api/communicate/references/{asset_id}", headers=auth_header(user_b["token"])).status_code == 404
    assert client.get(f"/api/communicate/references/{asset_id}/audio", headers=auth_header(user_b["token"])).status_code == 404
    assert (
        client.patch(
            f"/api/communicate/references/{asset_id}",
            headers=auth_header(user_b["token"]),
            json={"confirmed_category": "HOWL"},
        ).status_code
        == 404
    )
    assert (
        client.post(
            "/api/communicate/generate",
            headers=auth_header(user_b["token"]),
            json={"text": "come here", "reference_asset_id": asset_id},
        ).status_code
        == 400
    )

    # Clean up test-uploaded asset so production reference manifest stays pristine
    from app.services import reference_library as rl

    lib = rl.build_or_load_reference_library()
    remaining = [a for a in lib["assets"] if a["asset_id"] != asset_id]
    rl._MANIFEST_CACHE = rl._finalize_and_save_manifest(remaining)
    for f in rl.REF_RAW_DIR.glob(f"{asset_id}.*"):
        f.unlink(missing_ok=True)
    for f in rl.REF_PROC_DIR.glob(f"{asset_id}.*"):
        f.unlink(missing_ok=True)


def test_blind_listening_protocol_endpoints(client, user_a):
    r_bt = client.get("/api/communicate/blind-test", headers=auth_header(user_a["token"]))
    assert r_bt.status_code == 200
    data = r_bt.json()
    assert data["protocol_version"] == "1.0"
    assert data["human_listening_evaluation_status"] in {"PENDING", "PASS"}
    assert data["total_blind_samples"] == 44
    sample0 = data["samples"][0]
    assert "generation_method" not in sample0
    r_aud = client.get(sample0["audio_url"], headers=auth_header(user_a["token"]))
    assert r_aud.status_code == 200
    assert r_aud.content[:4] == b"RIFF"

