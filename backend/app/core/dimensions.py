"""
Dimension vocabulary and prompt slot descriptions.
All 14 preference dimensions, their discrete vocab options,
and their mapped float scores in [-1.0, +1.0].
"""

# Canonical ordered list of all 14 dimension names
ALL_DIMENSIONS = [
    "model_presence",
    "model_style",
    "skin_tone_preference",
    "pose_type",
    "framing",
    "product_position",
    "lighting_softness",
    "lighting_direction",
    "color_temperature",
    "background_complexity",
    "background_palette",
    "atmosphere",
    "retouch_intensity",
    "product_prominence",
]

# For each dimension: list of (vocab_word, float_score) tuples in ascending score order
DIMENSION_VOCAB: dict[str, list[tuple[str, float]]] = {
    "model_presence": [
        ("no_model", -1.0),
        ("hand_only", -0.33),
        ("partial_body", 0.33),
        ("full_model", 1.0),
    ],
    "model_style": [
        ("minimal", -1.0),
        ("lifestyle", -0.33),
        ("editorial", 0.33),
        ("luxury_editorial", 1.0),
    ],
    "skin_tone_preference": [
        ("porcelain", -1.0),
        ("medium", 0.0),
        ("deep", 1.0),
    ],
    "pose_type": [
        ("hand_closeup", -1.0),
        ("wrist_shot", -0.33),
        ("neck_collarbone", 0.33),
        ("full_ear_shot", 1.0),
    ],
    "framing": [
        ("extreme_macro", -1.0),
        ("close_crop", 0.0),
        ("medium_frame", 1.0),
    ],
    "product_position": [
        ("centered", -1.0),
        ("rule_of_thirds", 0.0),
        ("diagonal_emphasis", 1.0),
    ],
    "lighting_softness": [
        ("hard_dramatic", -1.0),
        ("mixed", 0.0),
        ("soft_diffused", 1.0),
    ],
    "lighting_direction": [
        ("front_flat", -1.0),
        ("top_down", -0.33),
        ("side_45_deg", 0.33),
        ("backlit_rim", 1.0),
    ],
    "color_temperature": [
        ("cool_daylight", -1.0),
        ("neutral_white", 0.0),
        ("warm_golden", 1.0),
    ],
    "background_complexity": [
        ("pure_white", -1.0),
        ("minimal_texture", -0.33),
        ("styled_scene", 0.33),
        ("rich_environment", 1.0),
    ],
    "background_palette": [
        ("white_clean", -1.0),
        ("neutral_beige", -0.33),
        ("dark_luxury", 0.33),
        ("jewel_tone", 1.0),
    ],
    "atmosphere": [
        ("clean_catalog", -1.0),
        ("premium_editorial", -0.33),
        ("romantic_soft", 0.33),
        ("bold_fashion", 1.0),
    ],
    "retouch_intensity": [
        ("natural_raw", -1.0),
        ("light_polish", 0.0),
        ("high_gloss", 1.0),
    ],
    "product_prominence": [
        ("subtle_styling", -1.0),
        ("balanced", 0.0),
        ("product_first", 1.0),
    ],
}

# Human-readable descriptions for each vocab word used in prompt compilation
PROMPT_SLOT_DESCRIPTIONS: dict[str, dict[str, str]] = {
    "framing": {
        "extreme_macro": "Extreme macro framing, jewelry fills 90%+ of frame, background barely visible, razor-sharp product detail.",
        "close_crop": "Close crop with jewelry filling 60-70% of frame, shallow depth of field, soft background blur.",
        "medium_frame": "Medium framing showing jewelry in full context, filling 40-50% of frame with surrounding environment.",
    },
    "product_position": {
        "centered": "Product perfectly centered in frame, symmetrical composition, equal negative space on all sides.",
        "rule_of_thirds": "Product positioned at rule-of-thirds intersection, off-center, dynamic but balanced.",
        "diagonal_emphasis": "Product placed along diagonal axis for energy and movement, leading line composition.",
    },
    "lighting_softness": {
        "hard_dramatic": "Hard directional light from a small source, sharp-edged shadows, strong specular highlights on metal and stones.",
        "mixed": "Mixed lighting: primary softbox with small fill card, moderate shadow definition, natural specular.",
        "soft_diffused": "Fully soft-diffused light from large area source (octabox), wrapping shadows, smooth gradients, minimal specular.",
    },
    "lighting_direction": {
        "front_flat": "Front-facing flat fill light on camera axis, minimal shadows, even illumination across product.",
        "top_down": "Top-down light at 45 degrees overhead, Rembrandt-style, strong highlight on upper facets of stones.",
        "side_45_deg": "45-degree side light from camera-left, creates depth and dimension in metal, reveals texture.",
        "backlit_rim": "Backlit with rim light separating jewelry from background, dramatic separation glow, moody.",
    },
    "color_temperature": {
        "cool_daylight": "Cool daylight color temperature (5500-6500K), crisp, clean, modern studio feel.",
        "neutral_white": "Neutral white balanced light (5000K), accurate color reproduction, no color cast.",
        "warm_golden": "Warm golden light (3000-4000K), rich and luxurious, flatters yellow gold and rose gold.",
    },
    "background_complexity": {
        "pure_white": "Pure seamless white background, no texture, no shadows, infinity cove look.",
        "minimal_texture": "Subtly textured background (fine linen, soft marble, matte paper), low distraction.",
        "styled_scene": "Styled flat-lay or tabletop scene with 1-2 complementary props (flowers, fabric, small objects).",
        "rich_environment": "Rich lifestyle environment (jewelry box on dresser, window light through sheer curtain, wooden surface with foliage).",
    },
    "background_palette": {
        "white_clean": "White or off-white background palette, bright and airy.",
        "neutral_beige": "Warm neutral beige, sand, or cream background palette.",
        "dark_luxury": "Deep charcoal, black, or dark navy background palette, opulent and dramatic.",
        "jewel_tone": "Rich jewel-tone background (deep emerald, sapphire blue, burgundy), maximalist luxury.",
    },
    "atmosphere": {
        "clean_catalog": "Clean commercial catalog aesthetic, no mood, pure product documentation.",
        "premium_editorial": "Premium editorial feel, intentional styling, sophisticated and aspirational.",
        "romantic_soft": "Romantic soft mood, dreamy, feminine, soft pastels and gentle bokeh.",
        "bold_fashion": "Bold high-fashion mood, strong contrast, directional, magazine cover energy.",
    },
    "retouch_intensity": {
        "natural_raw": "Natural, minimal retouching, authentic skin texture, realistic metal imperfections visible.",
        "light_polish": "Light commercial retouching, smooth skin, clean metal surfaces, subtle enhancement.",
        "high_gloss": "High-gloss commercial polish, mirror-finish metals, perfect skin, luxury catalogue standard.",
    },
    "product_prominence": {
        "subtle_styling": "Product is one element in a styled scene, environment is equally prominent.",
        "balanced": "Product and environment balanced, product clearly identifiable but not isolated.",
        "product_first": "Product is the undisputed hero, everything else serves to highlight the jewelry.",
    },
}

# Dislike chip tags
DISLIKE_CHIPS = [
    ("too_dark", "Too dark"),
    ("too_busy", "Too busy"),
    ("model_distracts", "Model distracts"),
    ("not_realistic", "Not realistic"),
    ("product_unclear", "Product unclear"),
    ("wrong_vibe", "Wrong vibe"),
]

# Like chip tags
LIKE_CHIPS = [
    ("love_lighting", "Love lighting"),
    ("great_composition", "Great composition"),
    ("model_works", "Model works"),
    ("premium_feel", "Premium feel"),
    ("product_pops", "Product pops"),
]

# Reason tag → affected dimensions (for amplification during profile update)
REASON_TAG_DIMENSION_MAP: dict[str, list[str]] = {
    "love_lighting": ["lighting_softness", "lighting_direction", "color_temperature"],
    "great_composition": ["framing", "product_position"],
    "model_works": ["model_presence", "model_style", "pose_type"],
    "premium_feel": ["atmosphere", "retouch_intensity", "background_palette"],
    "product_pops": ["product_prominence", "framing"],
    "too_dark": ["lighting_softness", "color_temperature"],
    "too_busy": ["background_complexity", "atmosphere"],
    "model_distracts": ["model_presence"],
    "not_realistic": ["retouch_intensity"],
    "product_unclear": ["product_prominence", "framing"],
    "wrong_vibe": ["atmosphere", "background_palette"],
}


def vocab_choice_to_float(dimension_name: str, vocab_word: str) -> float:
    """Map a vocab word back to its float score."""
    vocab = DIMENSION_VOCAB.get(dimension_name, [])
    for word, score in vocab:
        if word == vocab_word:
            return score
    return 0.0


def score_to_vocab_word(dimension_name: str, score: float) -> str:
    """Map a float score to the closest vocab word for that dimension."""
    vocab = DIMENSION_VOCAB.get(dimension_name, [])
    if not vocab:
        return ""
    best_word = vocab[0][0]
    best_dist = abs(vocab[0][1] - score)
    for word, v_score in vocab:
        dist = abs(v_score - score)
        if dist < best_dist:
            best_dist = dist
            best_word = word
    return best_word


def get_vocab_words(dimension_name: str) -> list[str]:
    """Return all vocab words for a dimension."""
    return [w for w, _ in DIMENSION_VOCAB.get(dimension_name, [])]
