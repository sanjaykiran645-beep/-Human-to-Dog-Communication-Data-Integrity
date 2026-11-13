"""
Silent Backend Canine Breed Intelligence & Bioacoustic Calibration Engine.
Fetches and synthesizes breed temperament, Stanley Coren intelligence tier,
vocalization tendencies, and fundamental pitch (F0 Hz) from a built-in knowledge
graph + live Wikipedia REST API lookup. Runs strictly in the backend.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import Any

BREED_DB: dict[str, dict[str, Any]] = {
    "golden retriever": {
        "canonical_breed": "Golden Retriever",
        "size_category": "large",
        "default_weight_kg": 30.0,
        "intelligence_rank": 4,
        "intelligence_tier": "Brightest Working & Obedience (Top 5%)",
        "temperament": ["friendly", "intelligent", "devoted", "eager_to_please", "social"],
        "vocalization_profile": {
            "bark_tendency": "moderate",
            "howl_tendency": "low",
            "whine_tendency": "moderate_attention_seeking",
            "dominant_cues": ["social_greeting_bark", "play_yip", "soft_attention_whine"],
            "f0_range_hz": [160, 420],
            "optimal_synth_pitch_hz": 280.0,
            "pitch_shift_semitones": -0.5,
        },
        "behavioral_priors": {
            "playfulness": 0.25,
            "social_interaction": 0.25,
            "attention_seeking": 0.20,
            "excitement": 0.18,
            "alerting_or_warning": 0.12,
        },
    },
    "american pit bull": {
        "canonical_breed": "American Pit Bull Terrier",
        "size_category": "medium_large",
        "default_weight_kg": 24.0,
        "intelligence_rank": 35,
        "intelligence_tier": "Above Average Working Dog",
        "temperament": ["confident", "alert", "loyal", "courageous", "high_drive"],
        "vocalization_profile": {
            "bark_tendency": "low_to_moderate",
            "howl_tendency": "low",
            "whine_tendency": "high_vocal_grumble_and_whine",
            "dominant_cues": ["excited_play_grunt", "alert_bark", "affectionate_whine"],
            "f0_range_hz": [140, 380],
            "optimal_synth_pitch_hz": 240.0,
            "pitch_shift_semitones": -1.0,
        },
        "behavioral_priors": {
            "excitement": 0.24,
            "playfulness": 0.22,
            "alerting_or_warning": 0.20,
            "territorial": 0.16,
            "attention_seeking": 0.18,
        },
    },
    "pit bull": {
        "canonical_breed": "American Pit Bull Terrier",
        "size_category": "medium_large",
        "default_weight_kg": 24.0,
        "intelligence_rank": 35,
        "intelligence_tier": "Above Average Working Dog",
        "temperament": ["confident", "alert", "loyal", "courageous", "high_drive"],
        "vocalization_profile": {
            "bark_tendency": "low_to_moderate",
            "howl_tendency": "low",
            "whine_tendency": "high_vocal_grumble_and_whine",
            "dominant_cues": ["excited_play_grunt", "alert_bark", "affectionate_whine"],
            "f0_range_hz": [140, 380],
            "optimal_synth_pitch_hz": 240.0,
            "pitch_shift_semitones": -1.0,
        },
        "behavioral_priors": {
            "excitement": 0.24,
            "playfulness": 0.22,
            "alerting_or_warning": 0.20,
            "territorial": 0.16,
            "attention_seeking": 0.18,
        },
    },
    "german shepherd": {
        "canonical_breed": "German Shepherd",
        "size_category": "large",
        "default_weight_kg": 34.0,
        "intelligence_rank": 3,
        "intelligence_tier": "Brightest Working & Obedience (Rank #3)",
        "temperament": ["watchful", "courageous", "intelligent", "protective", "focused"],
        "vocalization_profile": {
            "bark_tendency": "high_watch_alert",
            "howl_tendency": "moderate",
            "whine_tendency": "high_expressive_whine",
            "dominant_cues": ["territorial_alert_bark", "attention_whine", "command_grunt"],
            "f0_range_hz": [130, 390],
            "optimal_synth_pitch_hz": 230.0,
            "pitch_shift_semitones": -1.2,
        },
        "behavioral_priors": {
            "alerting_or_warning": 0.28,
            "territorial": 0.22,
            "attention_seeking": 0.20,
            "defensive_or_threat": 0.15,
            "excitement": 0.15,
        },
    },
    "labrador": {
        "canonical_breed": "Labrador Retriever",
        "size_category": "large",
        "default_weight_kg": 31.0,
        "intelligence_rank": 7,
        "intelligence_tier": "Brightest Working & Obedience (Top 10%)",
        "temperament": ["outgoing", "even_tempered", "gentle", "playful", "food_motivated"],
        "vocalization_profile": {
            "bark_tendency": "moderate",
            "howl_tendency": "low",
            "whine_tendency": "moderate",
            "dominant_cues": ["greeting_bark", "play_yip", "eager_whine"],
            "f0_range_hz": [150, 400],
            "optimal_synth_pitch_hz": 265.0,
            "pitch_shift_semitones": -0.6,
        },
        "behavioral_priors": {
            "playfulness": 0.26,
            "social_interaction": 0.24,
            "excitement": 0.22,
            "attention_seeking": 0.18,
            "alerting_or_warning": 0.10,
        },
    },
    "husky": {
        "canonical_breed": "Siberian Husky",
        "size_category": "medium_large",
        "default_weight_kg": 23.0,
        "intelligence_rank": 45,
        "intelligence_tier": "Independent Working Dog",
        "temperament": ["vocal", "outgoing", "mischievous", "pack_oriented", "energetic"],
        "vocalization_profile": {
            "bark_tendency": "low",
            "howl_tendency": "very_high_talking_howl",
            "whine_tendency": "high",
            "dominant_cues": ["social_howl", "expressive_whine", "play_yip"],
            "f0_range_hz": [180, 620],
            "optimal_synth_pitch_hz": 340.0,
            "pitch_shift_semitones": 0.4,
        },
        "behavioral_priors": {
            "social_interaction": 0.30,
            "attention_seeking": 0.25,
            "excitement": 0.20,
            "playfulness": 0.15,
            "frustration": 0.10,
        },
    },
    "beagle": {
        "canonical_breed": "Beagle",
        "size_category": "small_medium",
        "default_weight_kg": 11.0,
        "intelligence_rank": 72,
        "intelligence_tier": "Scenthound Specialist",
        "temperament": ["merry", "curious", "friendly", "pack_hound"],
        "vocalization_profile": {
            "bark_tendency": "high",
            "howl_tendency": "very_high_baying",
            "whine_tendency": "moderate",
            "dominant_cues": ["baying_howl", "excited_bark", "scent_yip"],
            "f0_range_hz": [240, 680],
            "optimal_synth_pitch_hz": 390.0,
            "pitch_shift_semitones": 0.9,
        },
        "behavioral_priors": {
            "excitement": 0.25,
            "social_interaction": 0.22,
            "alerting_or_warning": 0.20,
            "playfulness": 0.18,
            "attention_seeking": 0.15,
        },
    },
    "pug": {
        "canonical_breed": "Pug",
        "size_category": "small",
        "default_weight_kg": 8.0,
        "intelligence_rank": 57,
        "intelligence_tier": "Companion Specialist",
        "temperament": ["charming", "affectionate", "companionable", "playful"],
        "vocalization_profile": {
            "bark_tendency": "low",
            "howl_tendency": "low",
            "whine_tendency": "high_grumble_snort",
            "dominant_cues": ["social_grunt", "attention_whine", "play_yip"],
            "f0_range_hz": [260, 750],
            "optimal_synth_pitch_hz": 410.0,
            "pitch_shift_semitones": 1.1,
        },
        "behavioral_priors": {
            "attention_seeking": 0.28,
            "social_interaction": 0.26,
            "playfulness": 0.22,
            "excitement": 0.14,
            "distress_or_discomfort": 0.10,
        },
    },
    "rottweiler": {
        "canonical_breed": "Rottweiler",
        "size_category": "large",
        "default_weight_kg": 45.0,
        "intelligence_rank": 9,
        "intelligence_tier": "Brightest Working & Obedience (Rank #9)",
        "temperament": ["steady", "confident", "guardian", "calm", "courageous"],
        "vocalization_profile": {
            "bark_tendency": "low_measured_alert",
            "howl_tendency": "low",
            "whine_tendency": "moderate_rottie_rumble",
            "dominant_cues": ["deep_alert_bark", "low_rumble_grunt", "protective_growl"],
            "f0_range_hz": [95, 310],
            "optimal_synth_pitch_hz": 185.0,
            "pitch_shift_semitones": -1.6,
        },
        "behavioral_priors": {
            "alerting_or_warning": 0.28,
            "territorial": 0.25,
            "defensive_or_threat": 0.18,
            "social_interaction": 0.16,
            "attention_seeking": 0.13,
        },
    },
    "chihuahua": {
        "canonical_breed": "Chihuahua",
        "size_category": "toy",
        "default_weight_kg": 2.5,
        "intelligence_rank": 67,
        "intelligence_tier": "Alert Companion",
        "temperament": ["vigilant", "sassy", "devoted", "reactive"],
        "vocalization_profile": {
            "bark_tendency": "very_high",
            "howl_tendency": "low",
            "whine_tendency": "high",
            "dominant_cues": ["high_pitch_yip", "alert_bark", "anxious_whine"],
            "f0_range_hz": [380, 980],
            "optimal_synth_pitch_hz": 520.0,
            "pitch_shift_semitones": 1.6,
        },
        "behavioral_priors": {
            "alerting_or_warning": 0.26,
            "attention_seeking": 0.22,
            "fear_or_anxiety": 0.18,
            "excitement": 0.18,
            "territorial": 0.16,
        },
    },
    "indie": {
        "canonical_breed": "Indian Pariah Dog (Indie)",
        "size_category": "medium",
        "default_weight_kg": 18.0,
        "intelligence_rank": 15,
        "intelligence_tier": "High Adaptive & Survival Intelligence",
        "temperament": ["alert", "social", "intelligent", "territorial", "agile"],
        "vocalization_profile": {
            "bark_tendency": "moderate_to_high_watch",
            "howl_tendency": "moderate_pack_howl",
            "whine_tendency": "moderate",
            "dominant_cues": ["alert_bark", "social_howl", "play_yip"],
            "f0_range_hz": [170, 480],
            "optimal_synth_pitch_hz": 300.0,
            "pitch_shift_semitones": 0.0,
        },
        "behavioral_priors": {
            "alerting_or_warning": 0.25,
            "social_interaction": 0.22,
            "territorial": 0.20,
            "playfulness": 0.18,
            "attention_seeking": 0.15,
        },
    },
}

_WIKI_CACHE: dict[str, str] = {}


def _fetch_wikipedia_summary(breed_name: str) -> str:
    """Silently fetches breed summary from Wikipedia REST API with strict 1.5s timeout."""
    key = breed_name.strip().lower()
    if not key or key in _WIKI_CACHE:
        return _WIKI_CACHE.get(key, "")
    try:
        slug = urllib.parse.quote(breed_name.strip().title().replace(" ", "_"))
        url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{slug}"
        req = urllib.request.Request(url, headers={"User-Agent": "CanineSenseAI/2.0 (BioacousticEngine)"})
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                extract = str(data.get("extract") or "")[:600]
                _WIKI_CACHE[key] = extract
                return extract
    except Exception:
        pass
    _WIKI_CACHE[key] = ""
    return ""


def resolve_breed_intelligence(
    breed: str | None,
    weight_kg: float | None = None,
    age_years: float | None = None,
    fetch_remote: bool = False,
) -> dict[str, Any]:
    """Returns a complete hidden bioacoustic and behavioral intelligence profile for any dog."""
    raw = (breed or "").strip().lower()
    matched = None
    for k, profile in BREED_DB.items():
        if k in raw or raw in k:
            matched = dict(profile)
            break

    if matched is None:
        # Infer acoustic physics from weight or default medium canine
        w = float(weight_kg) if weight_kg else 20.0
        if w < 9.0:
            f0_range, synth_pitch, shift = [300, 820], 440.0, 1.0
            size_cat = "small"
        elif w > 28.0:
            f0_range, synth_pitch, shift = [120, 380], 235.0, -0.9
            size_cat = "large"
        else:
            f0_range, synth_pitch, shift = [170, 500], 310.0, 0.0
            size_cat = "medium"

        matched = {
            "canonical_breed": (breed or "Mixed Canine").strip().title(),
            "size_category": size_cat,
            "default_weight_kg": w,
            "intelligence_rank": 30,
            "intelligence_tier": "Adaptive Canine Intelligence",
            "temperament": ["attentive", "social", "responsive", "expressive"],
            "vocalization_profile": {
                "bark_tendency": "moderate",
                "howl_tendency": "moderate",
                "whine_tendency": "moderate",
                "dominant_cues": ["social_bark", "attention_whine", "play_yip"],
                "f0_range_hz": f0_range,
                "optimal_synth_pitch_hz": synth_pitch,
                "pitch_shift_semitones": shift,
            },
            "behavioral_priors": {
                "social_interaction": 0.24,
                "playfulness": 0.22,
                "attention_seeking": 0.22,
                "alerting_or_warning": 0.18,
                "excitement": 0.14,
            },
        }

    if fetch_remote and breed:
        wiki_extract = _fetch_wikipedia_summary(matched["canonical_breed"])
        if wiki_extract:
            matched["knowledge_source"] = "wikipedia_plus_caninesense_kb"
            matched["encyclopedia_summary"] = wiki_extract
        else:
            matched["knowledge_source"] = "caninesense_kb"
    else:
        matched["knowledge_source"] = "caninesense_kb"

    return matched
