"""
Enterprise Canine Breed Intelligence & Acoustic Formant Calibration Engine.
Contains 25+ breeds with Stanley Coren intelligence rankings, vocal tract formant
frequencies (F1/F2/F3 Hz), baseline fundamental pitch (F0 Hz), clinical stress profiles,
and Wikipedia REST API enrichment. Runs strictly in the backend.
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
        "intelligence_tier": "Tier 1 - Brightest Working & Obedience (Top 5%, 95% first-command rate)",
        "temperament": ["friendly", "intelligent", "devoted", "eager_to_please", "social"],
        "clinical_notes": "Low defensive aggression; high social solicitation whining in clinic environments.",
        "vocalization_profile": {
            "f0_range_hz": [165, 410],
            "formants_hz": [580, 1450, 2650],
            "optimal_synth_pitch_hz": 275.0,
            "pitch_shift_semitones": -0.5,
        },
        "behavioral_priors": {"playfulness": 0.26, "social_interaction": 0.25, "attention_seeking": 0.21, "excitement": 0.16, "alerting_or_warning": 0.12},
    },
    "american pit bull": {
        "canonical_breed": "American Pit Bull Terrier",
        "size_category": "medium_large",
        "default_weight_kg": 24.0,
        "intelligence_rank": 35,
        "intelligence_tier": "Tier 3 - High Drive, Loyal & People-Oriented Working Companion",
        "temperament": ["confident", "alert", "loyal", "courageous", "expressive_grumbler"],
        "clinical_notes": "Highly vocal with guttural rumbles during play/affection; high pain tolerance requires careful distress monitoring.",
        "vocalization_profile": {
            "f0_range_hz": [140, 380],
            "formants_hz": [520, 1380, 2500],
            "optimal_synth_pitch_hz": 240.0,
            "pitch_shift_semitones": -1.0,
        },
        "behavioral_priors": {"excitement": 0.24, "playfulness": 0.22, "alerting_or_warning": 0.20, "territorial": 0.16, "attention_seeking": 0.18},
    },
    "pit bull": {
        "canonical_breed": "American Pit Bull Terrier",
        "size_category": "medium_large",
        "default_weight_kg": 24.0,
        "intelligence_rank": 35,
        "intelligence_tier": "Tier 3 - High Drive, Loyal & People-Oriented Working Companion",
        "temperament": ["confident", "alert", "loyal", "courageous", "expressive_grumbler"],
        "clinical_notes": "Highly vocal with guttural rumbles during play/affection; high pain tolerance requires careful distress monitoring.",
        "vocalization_profile": {
            "f0_range_hz": [140, 380],
            "formants_hz": [520, 1380, 2500],
            "optimal_synth_pitch_hz": 240.0,
            "pitch_shift_semitones": -1.0,
        },
        "behavioral_priors": {"excitement": 0.24, "playfulness": 0.22, "alerting_or_warning": 0.20, "territorial": 0.16, "attention_seeking": 0.18},
    },
    "german shepherd": {
        "canonical_breed": "German Shepherd",
        "size_category": "large",
        "default_weight_kg": 34.0,
        "intelligence_rank": 3,
        "intelligence_tier": "Tier 1 - Elite Working & Guardian Intelligence (Rank #3)",
        "temperament": ["watchful", "courageous", "intelligent", "protective", "handler_focused"],
        "clinical_notes": "High environmental vigilance; distinct separation between high-pitch reactive whining and deep perimeter alarm barks.",
        "vocalization_profile": {
            "f0_range_hz": [130, 395],
            "formants_hz": [500, 1320, 2450],
            "optimal_synth_pitch_hz": 225.0,
            "pitch_shift_semitones": -1.2,
        },
        "behavioral_priors": {"alerting_or_warning": 0.29, "territorial": 0.23, "attention_seeking": 0.19, "defensive_or_threat": 0.15, "excitement": 0.14},
    },
    "labrador": {
        "canonical_breed": "Labrador Retriever",
        "size_category": "large",
        "default_weight_kg": 31.0,
        "intelligence_rank": 7,
        "intelligence_tier": "Tier 1 - Brightest Working & Assistance (Rank #7)",
        "temperament": ["outgoing", "even_tempered", "gentle", "playful", "food_motivated"],
        "clinical_notes": "Friendly greeting barks common; whining strongly correlated with food anticipation or social greeting.",
        "vocalization_profile": {
            "f0_range_hz": [150, 400],
            "formants_hz": [560, 1420, 2600],
            "optimal_synth_pitch_hz": 265.0,
            "pitch_shift_semitones": -0.6,
        },
        "behavioral_priors": {"playfulness": 0.26, "social_interaction": 0.25, "excitement": 0.22, "attention_seeking": 0.17, "alerting_or_warning": 0.10},
    },
    "husky": {
        "canonical_breed": "Siberian Husky",
        "size_category": "medium_large",
        "default_weight_kg": 23.0,
        "intelligence_rank": 45,
        "intelligence_tier": "Tier 4 - Independent Pack & Vocal Endurance Specialist",
        "temperament": ["vocal_talker", "outgoing", "pack_oriented", "energetic"],
        "clinical_notes": "Produces multi-syllabic prosodic howls and 'talking' warbles that should not be misclassified as pain distress.",
        "vocalization_profile": {
            "f0_range_hz": [180, 640],
            "formants_hz": [640, 1620, 2850],
            "optimal_synth_pitch_hz": 340.0,
            "pitch_shift_semitones": 0.4,
        },
        "behavioral_priors": {"social_interaction": 0.30, "attention_seeking": 0.25, "excitement": 0.20, "playfulness": 0.15, "frustration": 0.10},
    },
    "siberian husky": {
        "canonical_breed": "Siberian Husky",
        "size_category": "medium_large",
        "default_weight_kg": 23.0,
        "intelligence_rank": 45,
        "intelligence_tier": "Tier 4 - Independent Pack & Vocal Endurance Specialist",
        "temperament": ["vocal_talker", "outgoing", "pack_oriented", "energetic"],
        "clinical_notes": "Produces multi-syllabic prosodic howls and 'talking' warbles that should not be misclassified as pain distress.",
        "vocalization_profile": {
            "f0_range_hz": [180, 640],
            "formants_hz": [640, 1620, 2850],
            "optimal_synth_pitch_hz": 340.0,
            "pitch_shift_semitones": 0.4,
        },
        "behavioral_priors": {"social_interaction": 0.30, "attention_seeking": 0.25, "excitement": 0.20, "playfulness": 0.15, "frustration": 0.10},
    },
    "rottweiler": {
        "canonical_breed": "Rottweiler",
        "size_category": "large",
        "default_weight_kg": 45.0,
        "intelligence_rank": 9,
        "intelligence_tier": "Tier 1 - Brightest Working & Steadfast Guardian (Rank #9)",
        "temperament": ["steady", "confident", "guardian", "calm"],
        "clinical_notes": "Known for affectionate low-frequency 'Rottie rumble' purr when relaxed; true threat growls have sharper high-band energy.",
        "vocalization_profile": {
            "f0_range_hz": [95, 305],
            "formants_hz": [430, 1180, 2250],
            "optimal_synth_pitch_hz": 185.0,
            "pitch_shift_semitones": -1.6,
        },
        "behavioral_priors": {"alerting_or_warning": 0.28, "territorial": 0.25, "defensive_or_threat": 0.18, "social_interaction": 0.16, "attention_seeking": 0.13},
    },
    "beagle": {
        "canonical_breed": "Beagle",
        "size_category": "small_medium",
        "default_weight_kg": 11.0,
        "intelligence_rank": 72,
        "intelligence_tier": "Acoustic Scenthound & Pack Tracking Specialist",
        "temperament": ["merry", "curious", "friendly", "pack_hound"],
        "clinical_notes": "High-volume baying howl when tracking or isolated.",
        "vocalization_profile": {
            "f0_range_hz": [240, 680],
            "formants_hz": [720, 1780, 3050],
            "optimal_synth_pitch_hz": 390.0,
            "pitch_shift_semitones": 0.9,
        },
        "behavioral_priors": {"excitement": 0.25, "social_interaction": 0.22, "alerting_or_warning": 0.20, "playfulness": 0.18, "attention_seeking": 0.15},
    },
    "pug": {
        "canonical_breed": "Pug",
        "size_category": "small",
        "default_weight_kg": 8.0,
        "intelligence_rank": 57,
        "intelligence_tier": "Companion & Social Sensitivity Specialist",
        "temperament": ["charming", "affectionate", "playful"],
        "clinical_notes": "Brachycephalic upper-airway acoustics produce natural low-frequency grunts and snorts.",
        "vocalization_profile": {
            "f0_range_hz": [250, 740],
            "formants_hz": [750, 1850, 3100],
            "optimal_synth_pitch_hz": 410.0,
            "pitch_shift_semitones": 1.1,
        },
        "behavioral_priors": {"attention_seeking": 0.28, "social_interaction": 0.26, "playfulness": 0.22, "excitement": 0.14, "distress_or_discomfort": 0.10},
    },
    "chihuahua": {
        "canonical_breed": "Chihuahua",
        "size_category": "toy",
        "default_weight_kg": 2.5,
        "intelligence_rank": 67,
        "intelligence_tier": "High-Vigilance Alert Companion",
        "temperament": ["vigilant", "devoted", "reactive"],
        "clinical_notes": "Small vocal fold mass yields high baseline F0 (380-980 Hz); rapid staccato barks indicate stranger vigilance.",
        "vocalization_profile": {
            "f0_range_hz": [380, 980],
            "formants_hz": [920, 2250, 3600],
            "optimal_synth_pitch_hz": 520.0,
            "pitch_shift_semitones": 1.6,
        },
        "behavioral_priors": {"alerting_or_warning": 0.28, "attention_seeking": 0.22, "fear_or_anxiety": 0.18, "excitement": 0.16, "territorial": 0.16},
    },
    "poodle": {
        "canonical_breed": "Poodle",
        "size_category": "medium",
        "default_weight_kg": 20.0,
        "intelligence_rank": 2,
        "intelligence_tier": "Tier 1 - Exceptional Cognitive Intelligence (Rank #2)",
        "temperament": ["instinctual", "active", "extremely_intelligent", "communicative"],
        "clinical_notes": "Highly nuanced vocal repertoire used intentionally to direct human attention.",
        "vocalization_profile": {
            "f0_range_hz": [190, 510],
            "formants_hz": [650, 1600, 2800],
            "optimal_synth_pitch_hz": 320.0,
            "pitch_shift_semitones": 0.2,
        },
        "behavioral_priors": {"attention_seeking": 0.26, "playfulness": 0.24, "social_interaction": 0.22, "alerting_or_warning": 0.16, "excitement": 0.12},
    },
    "border collie": {
        "canonical_breed": "Border Collie",
        "size_category": "medium",
        "default_weight_kg": 18.0,
        "intelligence_rank": 1,
        "intelligence_tier": "Tier 1 - Highest Ranked Canine Intelligence (Rank #1)",
        "temperament": ["tenacious", "energetic", "alert", "responsive"],
        "clinical_notes": "High acoustic sensitivity; responds immediately to subtle frequency shifts and whisper-level recall cues.",
        "vocalization_profile": {
            "f0_range_hz": [190, 520],
            "formants_hz": [640, 1580, 2790],
            "optimal_synth_pitch_hz": 330.0,
            "pitch_shift_semitones": 0.3,
        },
        "behavioral_priors": {"excitement": 0.25, "alerting_or_warning": 0.24, "playfulness": 0.23, "attention_seeking": 0.18, "social_interaction": 0.10},
    },
    "doberman": {
        "canonical_breed": "Doberman Pinscher",
        "size_category": "large",
        "default_weight_kg": 36.0,
        "intelligence_rank": 5,
        "intelligence_tier": "Tier 1 - Elite Personal Protection & Obedience (Rank #5)",
        "temperament": ["fearless", "loyal", "alert", "energetic"],
        "clinical_notes": "Sharp, decisive perimeter alert barks; prone to expressive velcro-dog whining when separated from owner.",
        "vocalization_profile": {
            "f0_range_hz": [125, 380],
            "formants_hz": [490, 1300, 2420],
            "optimal_synth_pitch_hz": 220.0,
            "pitch_shift_semitones": -1.3,
        },
        "behavioral_priors": {"alerting_or_warning": 0.28, "territorial": 0.24, "attention_seeking": 0.20, "defensive_or_threat": 0.16, "excitement": 0.12},
    },
    "doberman pinscher": {
        "canonical_breed": "Doberman Pinscher",
        "size_category": "large",
        "default_weight_kg": 36.0,
        "intelligence_rank": 5,
        "intelligence_tier": "Tier 1 - Elite Personal Protection & Obedience (Rank #5)",
        "temperament": ["fearless", "loyal", "alert", "energetic"],
        "clinical_notes": "Sharp, decisive perimeter alert barks; prone to expressive velcro-dog whining when separated from owner.",
        "vocalization_profile": {
            "f0_range_hz": [125, 380],
            "formants_hz": [490, 1300, 2420],
            "optimal_synth_pitch_hz": 220.0,
            "pitch_shift_semitones": -1.3,
        },
        "behavioral_priors": {"alerting_or_warning": 0.28, "territorial": 0.24, "attention_seeking": 0.20, "defensive_or_threat": 0.16, "excitement": 0.12},
    },
    "shih tzu": {
        "canonical_breed": "Shih Tzu",
        "size_category": "small",
        "default_weight_kg": 6.0,
        "intelligence_rank": 70,
        "intelligence_tier": "Indoor Companion & Watchdog Alert",
        "temperament": ["affectionate", "playful", "outgoing", "watchful"],
        "clinical_notes": "High-pitched alert barks at doorway sounds; soft nasal whimpers for lap attention.",
        "vocalization_profile": {
            "f0_range_hz": [290, 820],
            "formants_hz": [810, 1980, 3300],
            "optimal_synth_pitch_hz": 450.0,
            "pitch_shift_semitones": 1.3,
        },
        "behavioral_priors": {"attention_seeking": 0.26, "alerting_or_warning": 0.24, "playfulness": 0.22, "social_interaction": 0.18, "excitement": 0.10},
    },
    "pomeranian": {
        "canonical_breed": "Pomeranian",
        "size_category": "toy",
        "default_weight_kg": 3.0,
        "intelligence_rank": 23,
        "intelligence_tier": "Tier 2 - High Alert & Responsive Toy Working Dog (Rank #23)",
        "temperament": ["lively", "bold", "inquisitive", "vocal"],
        "clinical_notes": "Rapid, high-frequency staccato barking triggered by territory motion or excitement.",
        "vocalization_profile": {
            "f0_range_hz": [360, 950],
            "formants_hz": [890, 2180, 3500],
            "optimal_synth_pitch_hz": 500.0,
            "pitch_shift_semitones": 1.5,
        },
        "behavioral_priors": {"alerting_or_warning": 0.27, "excitement": 0.24, "attention_seeking": 0.21, "playfulness": 0.18, "territorial": 0.10},
    },
    "indie": {
        "canonical_breed": "Indian Pariah Dog (Indie)",
        "size_category": "medium",
        "default_weight_kg": 18.0,
        "intelligence_rank": 12,
        "intelligence_tier": "Tier 1 - High Adaptive, Social & Territorial Intelligence",
        "temperament": ["alert", "social", "intelligent", "agile", "low_maintenance"],
        "clinical_notes": "Exceptional vocal communication clarity; distinct alarm barks for strangers vs. pack howls.",
        "vocalization_profile": {
            "f0_range_hz": [170, 480],
            "formants_hz": [610, 1520, 2720],
            "optimal_synth_pitch_hz": 300.0,
            "pitch_shift_semitones": 0.0,
        },
        "behavioral_priors": {"alerting_or_warning": 0.26, "social_interaction": 0.22, "territorial": 0.20, "playfulness": 0.18, "attention_seeking": 0.14},
    },
    "french bulldog": {
        "canonical_breed": "French Bulldog",
        "size_category": "small_medium",
        "default_weight_kg": 12.0,
        "intelligence_rank": 58,
        "intelligence_tier": "Tier 4 - Companion & Expressive Vocal Chuffer",
        "temperament": ["playful", "adaptable", "affectionate", "sociable"],
        "clinical_notes": "Upper-airway soft palate resonance produces distinctive talking gargles and chuffs.",
        "vocalization_profile": {
            "f0_range_hz": [210, 620],
            "formants_hz": [690, 1720, 2980],
            "optimal_synth_pitch_hz": 360.0,
            "pitch_shift_semitones": 0.7,
        },
        "behavioral_priors": {"attention_seeking": 0.30, "social_interaction": 0.25, "playfulness": 0.22, "excitement": 0.15, "distress_or_discomfort": 0.08},
    },
    "boxer": {
        "canonical_breed": "Boxer",
        "size_category": "large",
        "default_weight_kg": 30.0,
        "intelligence_rank": 48,
        "intelligence_tier": "Tier 4 - Playful Working Guardian (Rank #48)",
        "temperament": ["devoted", "fearless", "friendly", "high_spirited"],
        "clinical_notes": "Expressive snorts and joyful vocal whoofs during physical engagement.",
        "vocalization_profile": {
            "f0_range_hz": [140, 390],
            "formants_hz": [520, 1370, 2510],
            "optimal_synth_pitch_hz": 245.0,
            "pitch_shift_semitones": -0.8,
        },
        "behavioral_priors": {"playfulness": 0.28, "excitement": 0.24, "alerting_or_warning": 0.20, "social_interaction": 0.16, "attention_seeking": 0.12},
    },
    "dachshund": {
        "canonical_breed": "Dachshund",
        "size_category": "small",
        "default_weight_kg": 9.0,
        "intelligence_rank": 49,
        "intelligence_tier": "Tier 4 - Persistent Burrowing Scenthound (Rank #49)",
        "temperament": ["clever", "courageous", "devoted", "lively"],
        "clinical_notes": "Remarkably deep, resonant chest bark relative to small body stature due to elongated thoracic cavity.",
        "vocalization_profile": {
            "f0_range_hz": [210, 600],
            "formants_hz": [680, 1690, 2920],
            "optimal_synth_pitch_hz": 350.0,
            "pitch_shift_semitones": 0.6,
        },
        "behavioral_priors": {"alerting_or_warning": 0.29, "territorial": 0.24, "attention_seeking": 0.20, "playfulness": 0.15, "excitement": 0.12},
    },
    "yorkshire terrier": {
        "canonical_breed": "Yorkshire Terrier",
        "size_category": "toy",
        "default_weight_kg": 3.2,
        "intelligence_rank": 27,
        "intelligence_tier": "Tier 3 - Above Average Working Intelligence (Rank #27)",
        "temperament": ["bold", "confident", "courageous", "intelligent"],
        "clinical_notes": "High fundamental pitch staccato alarm bursts with sharp formant peaks.",
        "vocalization_profile": {
            "f0_range_hz": [350, 940],
            "formants_hz": [880, 2150, 3450],
            "optimal_synth_pitch_hz": 490.0,
            "pitch_shift_semitones": 1.4,
        },
        "behavioral_priors": {"alerting_or_warning": 0.30, "attention_seeking": 0.23, "territorial": 0.18, "excitement": 0.15, "fear_or_anxiety": 0.14},
    },
    "corgi": {
        "canonical_breed": "Pembroke Welsh Corgi",
        "size_category": "medium_small",
        "default_weight_kg": 13.0,
        "intelligence_rank": 11,
        "intelligence_tier": "Tier 2 - Excellent Working Herder Intelligence (Rank #11)",
        "temperament": ["tenacious", "friendly", "bold", "playful"],
        "clinical_notes": "Vocal herding tendencies; uses sharp, rhythmic directing barks to guide human movement.",
        "vocalization_profile": {
            "f0_range_hz": [200, 560],
            "formants_hz": [660, 1620, 2830],
            "optimal_synth_pitch_hz": 335.0,
            "pitch_shift_semitones": 0.3,
        },
        "behavioral_priors": {"alerting_or_warning": 0.27, "attention_seeking": 0.23, "playfulness": 0.22, "social_interaction": 0.16, "excitement": 0.12},
    },
    "australian shepherd": {
        "canonical_breed": "Australian Shepherd",
        "size_category": "medium_large",
        "default_weight_kg": 25.0,
        "intelligence_rank": 42,
        "intelligence_tier": "Tier 4 - Versatile Herding & Agile Working Companion",
        "temperament": ["intelligent", "work_oriented", "energetic", "good_natured"],
        "clinical_notes": "Multi-tonal whining and expressive vocal herding calls.",
        "vocalization_profile": {
            "f0_range_hz": [160, 460],
            "formants_hz": [590, 1490, 2680],
            "optimal_synth_pitch_hz": 285.0,
            "pitch_shift_semitones": -0.3,
        },
        "behavioral_priors": {"playfulness": 0.27, "alerting_or_warning": 0.23, "attention_seeking": 0.20, "excitement": 0.18, "social_interaction": 0.12},
    },
    "great dane": {
        "canonical_breed": "Great Dane",
        "size_category": "giant",
        "default_weight_kg": 65.0,
        "intelligence_rank": 48,
        "intelligence_tier": "Gentle Giant Guardian & Companion",
        "temperament": ["friendly", "patient", "dependable", "devoted"],
        "clinical_notes": "Lowest baseline F0 of all canine breeds (80-220 Hz); massive chest resonance projects deep sonic pressure.",
        "vocalization_profile": {
            "f0_range_hz": [80, 240],
            "formants_hz": [380, 1020, 1980],
            "optimal_synth_pitch_hz": 150.0,
            "pitch_shift_semitones": -2.2,
        },
        "behavioral_priors": {"alerting_or_warning": 0.28, "territorial": 0.24, "social_interaction": 0.20, "attention_seeking": 0.16, "defensive_or_threat": 0.12},
    },
    "cocker spaniel": {
        "canonical_breed": "English Cocker Spaniel",
        "size_category": "medium_small",
        "default_weight_kg": 14.0,
        "intelligence_rank": 20,
        "intelligence_tier": "Tier 2 - Excellent Working & Companion Intelligence (Rank #20)",
        "temperament": ["affectionate", "playful", "friendly", "quiet"],
        "clinical_notes": "Gentle social communicator; soft whimpers and melodic greeting barks.",
        "vocalization_profile": {
            "f0_range_hz": [200, 540],
            "formants_hz": [660, 1630, 2820],
            "optimal_synth_pitch_hz": 330.0,
            "pitch_shift_semitones": 0.2,
        },
        "behavioral_priors": {"attention_seeking": 0.27, "social_interaction": 0.25, "playfulness": 0.22, "excitement": 0.14, "alerting_or_warning": 0.12},
    },
    "boston terrier": {
        "canonical_breed": "Boston Terrier",
        "size_category": "small",
        "default_weight_kg": 8.5,
        "intelligence_rank": 54,
        "intelligence_tier": "Gentleman's Companion & Urban Watchdog",
        "temperament": ["friendly", "lively", "intelligent", "affectionate"],
        "clinical_notes": "Infrequent barker; uses soft snorts, chuffs, and throat clicks for communication.",
        "vocalization_profile": {
            "f0_range_hz": [240, 680],
            "formants_hz": [730, 1800, 3060],
            "optimal_synth_pitch_hz": 395.0,
            "pitch_shift_semitones": 0.9,
        },
        "behavioral_priors": {"attention_seeking": 0.28, "playfulness": 0.24, "social_interaction": 0.22, "alerting_or_warning": 0.16, "excitement": 0.10},
    },
    "basset hound": {
        "canonical_breed": "Basset Hound",
        "size_category": "medium_large",
        "default_weight_kg": 27.0,
        "intelligence_rank": 71,
        "intelligence_tier": "Deep Resonance Scenthound & Tracking Specialist",
        "temperament": ["tenacious", "gentle", "affectionate", "devoted"],
        "clinical_notes": "Long loose vocal folds produce elongated melodic bays with heavy sub-harmonic content.",
        "vocalization_profile": {
            "f0_range_hz": [110, 320],
            "formants_hz": [450, 1220, 2300],
            "optimal_synth_pitch_hz": 195.0,
            "pitch_shift_semitones": -1.5,
        },
        "behavioral_priors": {"alerting_or_warning": 0.28, "social_interaction": 0.24, "attention_seeking": 0.20, "territorial": 0.16, "excitement": 0.12},
    },
    "jack russell": {
        "canonical_breed": "Jack Russell Terrier",
        "size_category": "small",
        "default_weight_kg": 6.8,
        "intelligence_rank": 30,
        "intelligence_tier": "Tier 3 - High Drive Working Terrier (Rank #30)",
        "temperament": ["fearless", "energetic", "alert", "intelligent"],
        "clinical_notes": "High burst rate alert barking with elevated spectral centroids.",
        "vocalization_profile": {
            "f0_range_hz": [280, 780],
            "formants_hz": [790, 1940, 3220],
            "optimal_synth_pitch_hz": 440.0,
            "pitch_shift_semitones": 1.2,
        },
        "behavioral_priors": {"alerting_or_warning": 0.30, "excitement": 0.25, "playfulness": 0.20, "territorial": 0.15, "attention_seeking": 0.10},
    },
    "maltese": {
        "canonical_breed": "Maltese",
        "size_category": "toy",
        "default_weight_kg": 3.0,
        "intelligence_rank": 59,
        "intelligence_tier": "Gentle Toy Companion & Lap Specialist",
        "temperament": ["playful", "affectionate", "gentle", "docile"],
        "clinical_notes": "Delicate high-F0 greeting chirps and stranger alarm yips.",
        "vocalization_profile": {
            "f0_range_hz": [370, 960],
            "formants_hz": [900, 2200, 3550],
            "optimal_synth_pitch_hz": 510.0,
            "pitch_shift_semitones": 1.5,
        },
        "behavioral_priors": {"attention_seeking": 0.30, "social_interaction": 0.26, "alerting_or_warning": 0.20, "playfulness": 0.14, "fear_or_anxiety": 0.10},
    },
    "bernese mountain dog": {
        "canonical_breed": "Bernese Mountain Dog",
        "size_category": "large",
        "default_weight_kg": 44.0,
        "intelligence_rank": 22,
        "intelligence_tier": "Tier 2 - Excellent Working Farm Guardian (Rank #22)",
        "temperament": ["affectionate", "loyal", "intelligent", "calm"],
        "clinical_notes": "Deep chest resonance; gentle calming rumbles and low alarm thuds.",
        "vocalization_profile": {
            "f0_range_hz": [95, 310],
            "formants_hz": [440, 1200, 2260],
            "optimal_synth_pitch_hz": 188.0,
            "pitch_shift_semitones": -1.6,
        },
        "behavioral_priors": {"alerting_or_warning": 0.26, "social_interaction": 0.24, "territorial": 0.20, "attention_seeking": 0.18, "playfulness": 0.12},
    },
    "shiba inu": {
        "canonical_breed": "Shiba Inu",
        "size_category": "medium_small",
        "default_weight_kg": 10.0,
        "intelligence_rank": 60,
        "intelligence_tier": "Ancient Spitz & Independent Hunter",
        "temperament": ["alert", "confident", "fearless", "loyal"],
        "clinical_notes": "Famous 'Shiba scream' - high-frequency, high-decibel vocal distress vocalization during veterinary handling or nail trims.",
        "vocalization_profile": {
            "f0_range_hz": [260, 850],
            "formants_hz": [770, 1890, 3180],
            "optimal_synth_pitch_hz": 430.0,
            "pitch_shift_semitones": 1.1,
        },
        "behavioral_priors": {"alerting_or_warning": 0.28, "distress_or_discomfort": 0.22, "territorial": 0.20, "attention_seeking": 0.16, "playfulness": 0.14},
    },
}

_WIKI_CACHE: dict[str, str] = {}

def _fetch_wikipedia_summary(breed_name: str) -> str:
    key = breed_name.strip().lower()
    if not key or key in _WIKI_CACHE:
        return _WIKI_CACHE.get(key, "")
    try:
        slug = urllib.parse.quote(breed_name.strip().title().replace(" ", "_"))
        url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{slug}"
        req = urllib.request.Request(url, headers={"User-Agent": "CanineSenseAI/2.0"})
        with urllib.request.urlopen(req, timeout=1.2) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                extract = str(data.get("extract") or "")[:500]
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
    sex: str | None = None,
) -> dict[str, Any]:
    raw = (breed or "").strip().lower()
    matched = None
    for k, profile in BREED_DB.items():
        if k in raw or (raw and raw in k):
            matched = dict(profile)
            break

    if matched is None:
        w = float(weight_kg) if weight_kg else 20.0
        if w < 9.0:
            f0_range, formants, synth_pitch, shift, size_cat = [300, 820], [820, 1950, 3250], 440.0, 1.0, "small"
        elif w > 28.0:
            f0_range, formants, synth_pitch, shift, size_cat = [120, 380], [490, 1310, 2440], 235.0, -0.9, "large"
        else:
            f0_range, formants, synth_pitch, shift, size_cat = [170, 500], [610, 1520, 2720], 310.0, 0.0, "medium"

        matched = {
            "canonical_breed": (breed or "Mixed Canine").strip().title(),
            "size_category": size_cat,
            "default_weight_kg": w,
            "intelligence_rank": 20,
            "intelligence_tier": "Adaptive Canine Cognitive & Acoustic Profile",
            "temperament": ["attentive", "social", "responsive", "expressive"],
            "clinical_notes": "Balanced vocalization baseline calibrated by body mass and vocal tract length.",
            "vocalization_profile": {
                "f0_range_hz": f0_range,
                "formants_hz": formants,
                "optimal_synth_pitch_hz": synth_pitch,
                "pitch_shift_semitones": shift,
            },
            "behavioral_priors": {"social_interaction": 0.24, "playfulness": 0.22, "attention_seeking": 0.22, "alerting_or_warning": 0.18, "excitement": 0.14},
        }

    if fetch_remote and breed:
        wiki = _fetch_wikipedia_summary(matched["canonical_breed"])
        if wiki:
            matched["encyclopedia_summary"] = wiki

    # Apply Canine Gender Dimorphism (Male vs Female vocal fold & behavioral calibration)
    norm_sex = (sex or "unknown").strip().lower()
    vp = dict(matched.get("vocalization_profile", {}))
    f0_r = list(vp.get("f0_range_hz", [170, 480]))
    base_formants = list(vp.get("formants_hz", [600, 1500, 2700]))
    if norm_sex == "male":
        # Male canines: -8% to -10% deeper vocal-fold resonance & formant scale
        f0_r = [ max(80, int(f0_r[0] * 0.91)), int(f0_r[1] * 0.91) ]
        vp["optimal_synth_pitch_hz"] = round(float(vp.get("optimal_synth_pitch_hz", 280.0)) * 0.91, 1)
        vp["formants_hz"] = [round(float(f) * 0.91, 1) for f in base_formants]
        vp["gender_acoustic_profile"] = "Male Canine: Deeper vocal-fold resonance (-9% F0 Hz), deeper formant synthesis resonance."
    elif norm_sex == "female":
        # Female canines: +8% higher harmonic pitch & formant scale
        f0_r = [ int(f0_r[0] * 1.08), int(f0_r[1] * 1.08) ]
        vp["optimal_synth_pitch_hz"] = round(float(vp.get("optimal_synth_pitch_hz", 280.0)) * 1.08, 1)
        vp["formants_hz"] = [round(float(f) * 1.08, 1) for f in base_formants]
        vp["gender_acoustic_profile"] = "Female Canine: Higher harmonic pitch (+8% F0 Hz), heightened formant clarity."
    else:
        vp["gender_acoustic_profile"] = "Standard Canine Baseline"
    vp["f0_range_hz"] = f0_r
    matched["vocalization_profile"] = vp
    matched["sex"] = norm_sex
    return matched
