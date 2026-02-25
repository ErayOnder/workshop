"""
Cold start configs: 3 maximally diverse candidates for round 1.
Big questions first: model_presence, background_complexity, lighting_softness.
"""

# Default dimension values per jewelry category
CATEGORY_DEFAULTS: dict[str, dict[str, str]] = {
    "ring": {
        "model_presence": "hand_only",
        "model_style": "minimal",
        "skin_tone_preference": "medium",
        "pose_type": "hand_closeup",
        "framing": "close_crop",
        "product_position": "centered",
        "lighting_softness": "soft_diffused",
        "lighting_direction": "side_45_deg",
        "color_temperature": "neutral_white",
        "background_complexity": "minimal_texture",
        "background_palette": "neutral_beige",
        "atmosphere": "premium_editorial",
        "retouch_intensity": "light_polish",
        "product_prominence": "product_first",
    },
    "necklace": {
        "model_presence": "partial_body",
        "model_style": "editorial",
        "skin_tone_preference": "medium",
        "pose_type": "neck_collarbone",
        "framing": "medium_frame",
        "product_position": "centered",
        "lighting_softness": "soft_diffused",
        "lighting_direction": "side_45_deg",
        "color_temperature": "neutral_white",
        "background_complexity": "minimal_texture",
        "background_palette": "white_clean",
        "atmosphere": "premium_editorial",
        "retouch_intensity": "light_polish",
        "product_prominence": "balanced",
    },
    "bracelet": {
        "model_presence": "hand_only",
        "model_style": "lifestyle",
        "skin_tone_preference": "medium",
        "pose_type": "wrist_shot",
        "framing": "close_crop",
        "product_position": "rule_of_thirds",
        "lighting_softness": "mixed",
        "lighting_direction": "side_45_deg",
        "color_temperature": "neutral_white",
        "background_complexity": "minimal_texture",
        "background_palette": "neutral_beige",
        "atmosphere": "premium_editorial",
        "retouch_intensity": "light_polish",
        "product_prominence": "product_first",
    },
    "earrings": {
        "model_presence": "partial_body",
        "model_style": "editorial",
        "skin_tone_preference": "medium",
        "pose_type": "full_ear_shot",
        "framing": "close_crop",
        "product_position": "rule_of_thirds",
        "lighting_softness": "soft_diffused",
        "lighting_direction": "side_45_deg",
        "color_temperature": "neutral_white",
        "background_complexity": "pure_white",
        "background_palette": "white_clean",
        "atmosphere": "clean_catalog",
        "retouch_intensity": "light_polish",
        "product_prominence": "product_first",
    },
}

# Fallback defaults (no category specified)
DEFAULT_CONFIG: dict[str, str] = CATEGORY_DEFAULTS["ring"]


def build_cold_start_configs(category: str | None) -> list[dict[str, str]]:
    """
    Return 3 maximally diverse configs for round 1.
    Varies the 3 big-question dimensions:
      - model_presence: no_model / hand_only / partial_body
      - background_complexity: pure_white / minimal_texture / styled_scene
      - lighting_softness: soft_diffused / mixed / hard_dramatic
    Other dimensions use the category default.
    """
    base = CATEGORY_DEFAULTS.get(category or "", DEFAULT_CONFIG).copy()

    config_a = base.copy()
    config_a["model_presence"] = "no_model"
    config_a["background_complexity"] = "pure_white"
    config_a["lighting_softness"] = "soft_diffused"
    config_a["background_palette"] = "white_clean"
    config_a["atmosphere"] = "clean_catalog"

    config_b = base.copy()
    config_b["model_presence"] = "hand_only"
    config_b["background_complexity"] = "minimal_texture"
    config_b["lighting_softness"] = "mixed"
    config_b["background_palette"] = "neutral_beige"
    config_b["atmosphere"] = "premium_editorial"

    config_c = base.copy()
    config_c["model_presence"] = "partial_body"
    config_c["background_complexity"] = "styled_scene"
    config_c["lighting_softness"] = "hard_dramatic"
    config_c["lighting_direction"] = "side_45_deg"
    config_c["background_palette"] = "dark_luxury"
    config_c["atmosphere"] = "bold_fashion"

    return [config_a, config_b, config_c]
