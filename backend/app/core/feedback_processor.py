"""
Feedback processor.

Converts user feedback (action + chips + free text) into natural language
corrections and aesthetic tag updates that accumulate on the session's
creative_context. Replaces the old dimension-score preference engine.
"""
import copy

# ---------------------------------------------------------------------------
# Static chip → correction template mappings
# ---------------------------------------------------------------------------

_LIKE_CHIP_CORRECTIONS: dict[str, str] = {
    "love_lighting":     "PREFER: lighting quality and direction similar to the approved scene",
    "great_composition": "PREFER: compositional framing and product placement of the approved scene",
    "model_works":       "PREFER: model presence level and styling of the approved scene",
    "premium_feel":      "PREFER: premium editorial atmosphere and high-quality finish",
    "product_pops":      "PREFER: strong product visibility where the jewelry reads clearly at first glance",
}

_DISLIKE_CHIP_CORRECTIONS: dict[str, str] = {
    "too_dark":        "AVOID: underexposed scenes with heavy shadows that obscure the jewelry",
    "too_busy":        "AVOID: busy backgrounds with multiple competing visual elements",
    "model_distracts": "AVOID: model presence that competes with or overshadows the jewelry",
    "not_realistic":   "AVOID: over-stylized or illustrated-looking results",
    "product_unclear": "AVOID: compositions where the jewelry is difficult to read clearly",
    "wrong_vibe":      "AVOID: the atmosphere and mood of the rejected scene",
}

# Chips that imply a structural preference update
_STRUCTURAL_CHIP_UPDATES: dict[str, dict] = {
    "model_distracts": {"model": "none"},
    "model_works":     {},  # no update — keeps current
}

_EMPTY_CONTEXT: dict = {
    "structural": {},
    "corrections": [],
    "scene_history": [],
    "liked_tags": [],
    "disliked_tags": [],
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_corrections_and_updates(
    action: str,
    reason_tags: list[str],
    text_note: str | None,
    candidate_image_analysis: dict | None,
    candidate_aesthetic_tags: list[str],
) -> dict:
    """
    Derive corrections and tag updates from a single feedback submission.

    Returns:
        {
            "corrections": list[str],
            "liked_tags": list[str],
            "disliked_tags": list[str],
            "structural_update": dict | None,
        }
    """
    is_positive = action in ("like", "save")
    corrections: list[str] = []
    liked_tags: list[str] = []
    disliked_tags: list[str] = []
    structural_update: dict | None = None

    # 1. Free-text note → correction
    if text_note and text_note.strip():
        note = text_note.strip().rstrip(".")
        prefix = "PREFER" if is_positive else "AVOID"
        corrections.append(f"{prefix}: {note.lower()}")

    # 2. Static chip IDs → correction templates
    chip_map = _LIKE_CHIP_CORRECTIONS if is_positive else _DISLIKE_CHIP_CORRECTIONS
    for tag in reason_tags:
        if tag in chip_map:
            corrections.append(chip_map[tag])
        # Structural update
        if tag in _STRUCTURAL_CHIP_UPDATES and _STRUCTURAL_CHIP_UPDATES[tag]:
            structural_update = _STRUCTURAL_CHIP_UPDATES[tag]

    # 3. Dynamic chips from image analysis not covered by static map
    if candidate_image_analysis:
        all_chips = (
            candidate_image_analysis.get("like_chips", [])
            + candidate_image_analysis.get("dislike_chips", [])
        )
        chip_label_by_id = {c["id"]: c.get("label", "") for c in all_chips if isinstance(c, dict)}
        for tag in reason_tags:
            if tag not in chip_map and tag in chip_label_by_id:
                label = chip_label_by_id[tag].rstrip(".").lower()
                prefix = "PREFER" if is_positive else "AVOID"
                corrections.append(f"{prefix}: {label}")

    # 4. Aesthetic tags
    if is_positive:
        liked_tags = list(candidate_aesthetic_tags)
    else:
        disliked_tags = list(candidate_aesthetic_tags)

    return {
        "corrections": corrections,
        "liked_tags": liked_tags,
        "disliked_tags": disliked_tags,
        "structural_update": structural_update,
    }


def update_creative_context(
    context: dict,
    new_corrections: list[str],
    liked_tags: list[str],
    disliked_tags: list[str],
    structural_update: dict | None,
    scene_to_add_to_history: str | None,
) -> dict:
    """
    Return an updated copy of creative_context with the supplied changes merged in.
    Never mutates the input dict.
    """
    ctx = copy.deepcopy(context)
    # Ensure all keys exist
    ctx.setdefault("structural", {})
    ctx.setdefault("corrections", [])
    ctx.setdefault("scene_history", [])
    ctx.setdefault("liked_tags", [])
    ctx.setdefault("disliked_tags", [])

    # Corrections — deduplicate by exact string
    existing_corrections = set(ctx["corrections"])
    for c in new_corrections:
        if c not in existing_corrections:
            ctx["corrections"].append(c)
            existing_corrections.add(c)

    # Tags — deduplicate; moving a tag from liked→disliked removes it from liked
    existing_liked = set(ctx["liked_tags"])
    existing_disliked = set(ctx["disliked_tags"])

    for tag in liked_tags:
        if tag not in existing_liked:
            ctx["liked_tags"].append(tag)
            existing_liked.add(tag)

    for tag in disliked_tags:
        if tag in existing_liked:
            ctx["liked_tags"] = [t for t in ctx["liked_tags"] if t != tag]
            existing_liked.discard(tag)
        if tag not in existing_disliked:
            ctx["disliked_tags"].append(tag)
            existing_disliked.add(tag)

    # Structural update
    if structural_update:
        ctx["structural"].update(structural_update)

    # Scene history — cap at 15 entries
    if scene_to_add_to_history:
        ctx["scene_history"].append(scene_to_add_to_history)
        if len(ctx["scene_history"]) > 15:
            ctx["scene_history"] = ctx["scene_history"][-15:]

    return ctx
