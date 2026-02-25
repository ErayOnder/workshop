"""
Prompt agent: reads user profile + session state,
generates 3 diverse structured configs,
compiles each into a specific Gemini text prompt.
"""
import random
from .dimensions import (
    ALL_DIMENSIONS,
    DIMENSION_VOCAB,
    PROMPT_SLOT_DESCRIPTIONS,
    score_to_vocab_word,
    get_vocab_words,
)
from .cold_start import build_cold_start_configs


# --------------------------------------------------------------------------- #
# Candidate selection                                                          #
# --------------------------------------------------------------------------- #

def _staggered_epsilon(slot_index: int, round_number: int, exploit_mode: bool) -> float:
    """Return epsilon for this slot given the current round and exploitation state."""
    if exploit_mode:
        return [0.05, 0.2, 0.35][slot_index]
    if round_number <= 3:
        return [0.3, 0.6, 0.9][slot_index]
    if round_number <= 8:
        return [0.15, 0.35, 0.55][slot_index]
    return [0.1, 0.25, 0.4][slot_index]


def _greedy_config(profile_scores: dict[str, float]) -> dict[str, str]:
    """Build the greedy config: closest vocab word to current profile score per dimension."""
    return {dim: score_to_vocab_word(dim, profile_scores.get(dim, 0.0)) for dim in ALL_DIMENSIONS}


def _perturb_config(config: dict[str, str], epsilon: float) -> dict[str, str]:
    """Randomly replace dimension vocab words with probability epsilon, ensuring diversity."""
    result = config.copy()
    for dim in ALL_DIMENSIONS:
        if random.random() < epsilon:
            words = get_vocab_words(dim)
            if len(words) > 1:
                current = result[dim]
                alternatives = [w for w in words if w != current]
                result[dim] = random.choice(alternatives)
    return result


def generate_three_configs(
    profile_scores: dict[str, float],
    round_number: int,
    category: str | None,
    exploit_mode: bool = False,
) -> list[dict[str, str]]:
    """
    Generate 3 diverse structured attribute configs for the next round.
    Round 1 always uses cold-start diversity.
    """
    if round_number == 1:
        return build_cold_start_configs(category)

    greedy = _greedy_config(profile_scores)
    configs = []
    for slot_idx in range(3):
        eps = _staggered_epsilon(slot_idx, round_number, exploit_mode)
        candidate = _perturb_config(greedy, eps)
        configs.append(candidate)

    return configs


# --------------------------------------------------------------------------- #
# Prompt compilation                                                           #
# --------------------------------------------------------------------------- #

def _model_section(config: dict[str, str]) -> str:
    model_presence = config.get("model_presence", "no_model")
    model_style = config.get("model_style", "minimal")
    skin_tone = config.get("skin_tone_preference", "medium")
    pose = config.get("pose_type", "hand_closeup")

    skin_desc = {
        "porcelain": "porcelain / fair",
        "medium": "medium / tan",
        "deep": "deep / dark",
    }.get(skin_tone, "medium")

    pose_desc = {
        "hand_closeup": "single hand elegantly displaying the piece, fingers relaxed and natural",
        "wrist_shot": "wrist and forearm shown, piece worn naturally",
        "neck_collarbone": "neck and collarbone area, piece resting on décolleté",
        "full_ear_shot": "side profile of head showing ear, piece displayed prominently",
    }.get(pose, "hand closeup")

    style_desc = {
        "minimal": "clean minimal styling, no visible clothing distractions",
        "lifestyle": "casual lifestyle styling, natural and approachable",
        "editorial": "editorial fashion styling, intentional and curated",
        "luxury_editorial": "high-end luxury editorial styling, designer wardrobe elements",
    }.get(model_style, "minimal")

    if model_presence == "no_model":
        return (
            "NO MODEL: Pure product-only shot. Absolutely no human skin, fingers, hands, or body parts visible anywhere in the frame."
        )
    elif model_presence == "hand_only":
        return (
            f"HAND SHOT: A single elegant hand with {skin_desc} skin tone displaying the jewelry. "
            f"{pose_desc.capitalize()}. Nails well-groomed, no face visible. "
            f"Styling: {style_desc}."
        )
    elif model_presence == "partial_body":
        return (
            f"PARTIAL BODY SHOT: {pose_desc.capitalize()}. "
            f"Model has {skin_desc} skin tone. No face required. "
            f"Styling: {style_desc}."
        )
    else:  # full_model
        return (
            f"FULL MODEL SHOT: {pose_desc.capitalize()}. "
            f"Model with {skin_desc} skin tone in {style_desc}. "
            "Model's face may be partially visible but jewelry is the focal point."
        )


def compile_prompt(config: dict[str, str]) -> str:
    """
    Convert a structured attribute config dict into a detailed, specific Gemini text prompt.
    """
    framing = PROMPT_SLOT_DESCRIPTIONS["framing"].get(config.get("framing", "close_crop"), "")
    product_pos = PROMPT_SLOT_DESCRIPTIONS["product_position"].get(config.get("product_position", "centered"), "")
    light_soft = PROMPT_SLOT_DESCRIPTIONS["lighting_softness"].get(config.get("lighting_softness", "soft_diffused"), "")
    light_dir = PROMPT_SLOT_DESCRIPTIONS["lighting_direction"].get(config.get("lighting_direction", "side_45_deg"), "")
    color_temp = PROMPT_SLOT_DESCRIPTIONS["color_temperature"].get(config.get("color_temperature", "neutral_white"), "")
    bg_complex = PROMPT_SLOT_DESCRIPTIONS["background_complexity"].get(config.get("background_complexity", "minimal_texture"), "")
    bg_palette = PROMPT_SLOT_DESCRIPTIONS["background_palette"].get(config.get("background_palette", "neutral_beige"), "")
    atmosphere = PROMPT_SLOT_DESCRIPTIONS["atmosphere"].get(config.get("atmosphere", "premium_editorial"), "")
    retouch = PROMPT_SLOT_DESCRIPTIONS["retouch_intensity"].get(config.get("retouch_intensity", "light_polish"), "")
    prominence = PROMPT_SLOT_DESCRIPTIONS["product_prominence"].get(config.get("product_prominence", "product_first"), "")
    model_section = _model_section(config)

    prompt = f"""Photorealistic commercial jewelry photograph. Instagram-ready, square format (1:1 aspect ratio), ultra-high resolution (minimum 1080x1080 equivalent). Shot on professional medium-format camera equivalent.

PRODUCT FIDELITY — ABSOLUTE REQUIREMENTS (non-negotiable):
- Reproduce the EXACT jewelry piece from the reference image: identical metal color, stone count, stone shape, stone color, clasp design, setting style, and proportions
- Zero geometric distortion or warping of the product
- Product is always sharp and in critical focus
- No added decorative elements, engravings, or embellishments not present in reference

COMPOSITION:
- Framing: {framing}
- Product position: {product_pos}

LIGHTING SETUP:
- Quality: {light_soft}
- Direction: {light_dir}
- Color temperature: {color_temp}

BACKGROUND & ENVIRONMENT:
- Complexity: {bg_complex}
- Palette: {bg_palette}
- Atmosphere: {atmosphere}

SUBJECT / MODEL:
{model_section}

POST-PRODUCTION & FINISH:
- Retouching level: {retouch}
- Product prominence: {prominence}

TECHNICAL OUTPUT REQUIREMENTS:
- Photorealistic, not illustrated or stylized
- No text overlays, watermarks, or logos
- No props, objects, or elements not described above
- Correct perspective — no fish-eye, no extreme distortion
- Color-accurate representation of metal and stones"""

    return prompt
