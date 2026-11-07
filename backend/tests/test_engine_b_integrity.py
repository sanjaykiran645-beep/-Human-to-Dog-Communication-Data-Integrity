"""Engine B integrity tests: artifact detection, output QC gate, honest method labelling."""

import numpy as np
import pytest

from app.config import TARGET_SR
from app.services.reference_engine import (
    detect_transient_artifacts,
    generate_reference_driven_audio,
    validate_output_audio,
)


def _tone(n=TARGET_SR // 2):
    t = np.arange(n) / TARGET_SR
    y = 0.4 * np.sin(2 * np.pi * 440 * t) * np.hanning(n)
    return y.astype(np.float32)


def test_detector_clean_tone_has_no_clicks():
    a = detect_transient_artifacts(_tone())
    assert a["click_count"] == 0 and not a["edge_discontinuity"]


def test_detector_flags_injected_clicks_and_clipping():
    y = _tone()
    y[3000] += 0.9
    y[7000] -= 0.9
    assert detect_transient_artifacts(y)["click_count"] >= 2
    assert detect_transient_artifacts(np.clip(_tone() * 5, -1, 1))["clipped_ratio"] > 0.01


def test_output_gate_rejects_nan_silence_and_scales_peak():
    bad = _tone()
    bad[10] = np.nan
    with pytest.raises(ValueError):
        validate_output_audio(bad)
    with pytest.raises(ValueError):
        validate_output_audio(np.zeros(TARGET_SR, dtype=np.float32))
    hot = validate_output_audio(_tone() * 2.4)
    assert float(np.max(np.abs(hot))) <= 0.98 + 1e-6


def test_method_c_is_never_labelled_as_model_generated():
    y, p = generate_reference_driven_audio("BARK", generation_method="generative_model")
    assert p["generation_method"] == "reference_variation"
    assert p["requested_generation_method"] == "generative_model"
    assert p["method_substituted"] is True
    assert any("METHOD C UNAVAILABLE" in w for w in p["generation_warnings"])
    assert np.all(np.isfinite(y))


def test_method_c_strict_is_blocked():
    with pytest.raises(ValueError):
        generate_reference_driven_audio("BARK", generation_method="generative_model", strict_model_only=True)


@pytest.mark.parametrize("cat", ["BARK", "GROWL", "HOWL", "WHINE", "YIP", "YELP", "WHIMPER", "CRY", "GRUNT", "GROAN", "PANT"])
def test_dsp_supports_all_11_categories_with_dedicated_profiles_and_variations(cat):
    y0, p0 = generate_reference_driven_audio(cat, generation_method="experimental_dsp", variation_index=0)
    y1, p1 = generate_reference_driven_audio(cat, generation_method="experimental_dsp", variation_index=1)
    assert p0["vocalization"] == cat.lower()
    assert p0["synthetic"] is True
    assert np.all(np.isfinite(y0)) and np.all(np.isfinite(y1))
    assert y0.shape != y1.shape or not np.allclose(y0, y1)


@pytest.mark.parametrize("cat", ["BARK", "GROWL", "HOWL", "WHINE", "YIP", "YELP", "WHIMPER", "CRY", "GRUNT", "GROAN", "PANT"])
@pytest.mark.parametrize("method", ["reference_direct", "reference_variation"])
def test_reference_outputs_pass_technical_gate(cat, method):
    y, p = generate_reference_driven_audio(cat, generation_method=method)
    assert np.all(np.isfinite(y)) and float(np.max(np.abs(y))) <= 0.98 + 1e-6
    assert p["synthetic"] is False
    assert p["is_reference_recording"] == (method == "reference_direct")
    assert p["primary_reference_asset"]["label_verification"] in {
        "verified_by_named_reviewer",
        "unverified_source_or_curated_label",
    }
