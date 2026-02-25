"""
Preference learning engine.
Computes rewards and updates user profile dimension scores.
"""
from .dimensions import (
    ALL_DIMENSIONS,
    REASON_TAG_DIMENSION_MAP,
    vocab_choice_to_float,
)


def base_learning_rate(confidence: float) -> float:
    """LR decays from 0.35 (new user) to 0.05 (confident profile)."""
    return max(0.05, 0.35 * (1.0 - confidence))


def clamp(value: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def compute_reward(action: str) -> float:
    """Base reward by action type."""
    return {"like": 1.0, "dislike": -1.0, "save": 4.0}.get(action, 0.0)


def update_profile_from_feedback(
    dim_scores: dict[str, float],
    dim_confidences: dict[str, float],
    dim_counts: dict[str, int],
    candidate_config: dict[str, str],
    action: str,
    reason_tags: list[str],
) -> tuple[dict[str, float], dict[str, float], dict[str, int]]:
    """
    Update dimension scores based on user feedback.
    Returns updated (scores, confidences, counts) dicts.
    """
    reward = compute_reward(action)
    if reward == 0.0:
        return dim_scores, dim_confidences, dim_counts

    # Build amplification map from reason tags
    amplified_dims: set[str] = set()
    for tag in reason_tags:
        amplified_dims.update(REASON_TAG_DIMENSION_MAP.get(tag, []))

    new_scores = dict(dim_scores)
    new_confidences = dict(dim_confidences)
    new_counts = dict(dim_counts)

    for dim_name in ALL_DIMENSIONS:
        vocab_word = candidate_config.get(dim_name)
        if not vocab_word:
            continue

        choice_score = vocab_choice_to_float(dim_name, vocab_word)
        current_score = dim_scores.get(dim_name, 0.0)
        current_conf = dim_confidences.get(dim_name, 0.0)

        lr = base_learning_rate(current_conf)
        amplification = 1.5 if dim_name in amplified_dims else 1.0

        if reward > 0:
            # Move score toward the liked attribute value
            delta = lr * amplification * (choice_score - current_score)
        else:
            # Move score away from the disliked attribute value
            delta = lr * amplification * (current_score - choice_score) * abs(reward)

        new_scores[dim_name] = clamp(current_score + delta)
        new_confidences[dim_name] = min(1.0, current_conf + 0.05)
        new_counts[dim_name] = dim_counts.get(dim_name, 0) + 1

    return new_scores, new_confidences, new_counts


def blend_session_into_longterm(
    longterm_scores: dict[str, float],
    session_scores: dict[str, float],
    alpha: float = 0.15,
) -> dict[str, float]:
    """
    Merge session scores back into long-term profile at session end.
    alpha = weight given to session; (1-alpha) = long-term retention.
    """
    result = {}
    for dim in ALL_DIMENSIONS:
        lt = longterm_scores.get(dim, 0.0)
        sess = session_scores.get(dim, lt)  # fallback to lt if no session update
        result[dim] = clamp((1.0 - alpha) * lt + alpha * sess)
    return result


def should_exploit(
    round_number: int,
    save_pressed: bool,
    consecutive_likes: int,
) -> bool:
    """Determine if we should switch to exploitation mode."""
    return save_pressed or consecutive_likes >= 3
