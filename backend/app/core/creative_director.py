"""
LLM-as-Creative-Director.

Makes a single text-only Gemini Flash call per round to generate 3 complete,
structured scene briefs. Each brief uses an 8-field prompt schema that maps
directly to what makes a great jewelry photograph:

  1. format_medium     — capture format and quality baseline
  2. subject           — jewelry + model presence description
  3. camera_framing    — focal length, distance, crop, depth of field
  4. scene_setting     — location, environment, period
  5. micro_details     — material textures, surface qualities
  6. product_action    — how the jewelry is positioned or worn
  7. lighting          — source, quality, direction, colour temperature
  8. negative_cues     — explicit avoids

The 8 fields are then compiled into a structured text prompt for the image
generation API. The structure is stored on the candidate (in generation_config)
for precise feedback attribution.
"""
import json
import logging

from google import genai
from google.genai import types

from ..config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Structural constraint text
# ---------------------------------------------------------------------------

_MODEL_CONSTRAINTS: dict[str, str] = {
    "none":    "No human skin, hands, or body parts visible in any scene.",
    "hand":    "Exactly one hand may appear. No face visible.",
    "partial": "Partial body (hand, wrist, neck/collarbone, or ear) may appear. No face required.",
    "full":    "Full model may appear. Face may be partially visible. Jewelry remains the primary focus.",
}
_MODEL_CONSTRAINT_DEFAULT = "Open — choose whatever model presence best serves each scene."

_DOMINANCE_CONSTRAINTS: dict[str, str] = {
    "hero":     "The jewelry is the undisputed hero. All compositional choices serve to foreground the piece.",
    "balanced": "Jewelry and environment share equal visual weight.",
    "subtle":   "The environment is equally prominent. Jewelry is present but contextual.",
}
_DOMINANCE_CONSTRAINT_DEFAULT = "Open — choose whatever product dominance best serves each scene."

_CATEGORY_DESCRIPTIONS: dict[str, str] = {
    "ring":     "Ring — finger jewelry. Compositions often feature close-up hand shots or macro details of the band and stone.",
    "necklace": "Necklace — neck/collarbone jewelry. Partial body shots showing décolleté or pendant close-ups work well.",
    "bracelet": "Bracelet — wrist jewelry. Wrist and forearm shots are natural but not required.",
    "earrings": "Earrings — ear jewelry. Side profiles and close-ups of the earlobe area work well.",
}
_CATEGORY_DEFAULT = "Jewelry type unspecified — choose the most visually compelling compositions."

# ---------------------------------------------------------------------------
# Product fidelity block — injected into every compiled prompt
# ---------------------------------------------------------------------------

_PRODUCT_FIDELITY = (
    "PRODUCT FIDELITY: Reproduce the exact jewelry piece from the reference image with "
    "identical metal colour, stone count, stone shape, stone colour, clasp design, setting "
    "style, and proportions. Zero geometric distortion. Product always in critical focus."
)

# ---------------------------------------------------------------------------
# Meta-prompt
# ---------------------------------------------------------------------------

_META_PROMPT_TEMPLATE = """\
You are a world-class jewelry photography creative director with encyclopedic knowledge of \
art history, fashion photography, cinema, documentary, travel photography, and global visual culture.

Your task: generate exactly 3 structured scene briefs for a jewelry photoshoot. Each brief \
uses a strict 8-field schema that produces highly specific, executable instructions for an \
AI image generation model.

=== JEWELRY ===
{category_description}

=== STRUCTURAL CONSTRAINTS (apply to ALL three scenes — non-negotiable) ===
Model presence: {model_constraint}
Product dominance: {dominance_constraint}

=== SESSION MEMORY ===
This is round {round_number} of an ongoing creative session.

Previously generated scenes — DO NOT repeat any of these:
{scene_history_block}

Corrections — apply these to EVERY scene you generate:
{corrections_block}

Aesthetics the client responded to positively:
{liked_tags_block}

Aesthetics the client responded to negatively:
{disliked_tags_block}

=== CREATIVE MANDATE ===
Draw on the full breadth of human visual culture. The full range is available: Italian \
neorealism, Japanese wabi-sabi, 1970s Slim Aarons poolside photography, Moroccan riads at \
dusk, Soviet constructivism, film noir chiaroscuro, brutalist concrete, Bollywood golden-hour \
chromatics, Art Nouveau botanical illustration, Tudor portraiture sidelighting, Georgian \
silversmith workshops, Tokyo neon-wet streets, Icelandic lava fields at blue hour, Parisian \
atelier morning light, sub-Saharan textile colour, Californian surf bleached light — anything \
that serves the jewelry.

=== SLOT ASSIGNMENT ===
SLOT 0 — "converge": Refine what the client has responded to positively. All corrections \
applied. Stay within their preferred aesthetic but make it more resolved and specific.

SLOT 1 — "explore": Different aesthetic world from slot 0. Same structural constraints and \
corrections. If slot 0 is warm and intimate, slot 1 should be architectural and cool.

SLOT 2 — "wildcard": Maximum creative latitude. Something the client has not seen. \
Hard constraints and corrections still apply.

=== 8-FIELD SCHEMA ===
For each scene, populate all 8 fields:

1. format_medium — The capture format and quality baseline.
   Examples: "Ultra-realistic medium format still, Hasselblad equivalent, 1:1 crop"
             "Hyper-realistic iPhone 16 Pro video still, 9:16 vertical, grain texture"
             "Large-format film still, Kodak Ektar 100 colour negative, 1:1"

2. subject — The jewelry piece and how it is presented. Include model type if applicable.
   Examples: "Gold signet ring worn on the index finger of a female hand, medium skin tone, clean nails"
             "Diamond pendant necklace resting on bare décolleté, partial body shot, no face"
             "Pearl drop earrings displayed on a velvet pillow, no model"

3. camera_framing — Focal length character, working distance, framing, depth of field.
   Examples: "100mm macro equivalent, 20cm from subject, ring fills 65% of frame, f/2.8, \
              background dissolves to soft blur"
             "85mm portrait equivalent, waist-up framing, jewelry at rule-of-thirds, f/1.8"

4. scene_setting — Specific location, environment, period, and surfaces present.
   Examples: "Aged walnut writing desk in a 1930s Viennese apartment, afternoon light, \
              scattered manuscript pages"
             "Volcanic obsidian rock at Icelandic coastal lava field, blue hour, steam rising"
             "Pristine white seamless paper background, minimalist studio"

5. micro_details — Material textures and surface qualities visible in the frame.
   Examples: "Visible stone facets catching the light, fine grain on gold surface, \
              natural skin pores, dust motes in background"
             "Worn linen texture, water condensation on metal, aged wood grain"

6. product_action — Exact positioning or interaction of the jewelry in the scene.
   Examples: "Ring balanced on the rim of a crystal glass, reflection visible on glass surface"
             "Necklace laid flat on surface, chain arranged in a loose S-curve"
             "Ring worn on index finger, hand in relaxed open palm facing up"

7. lighting — Complete lighting setup: source, quality, direction, colour temperature.
   Examples: "Single bare tungsten bulb overhead at 2700K, hard shadows, specular \
              highlights on metal facets, no fill"
             "Soft north-facing window light, 5500K daylight, diffused by sheer linen \
              curtain, wrap-around shadows, catch light in stones"
             "Rim backlight from below, blue-hour ambient fill, separation glow on metal edges"

8. negative_cues — Explicit list of things that must NOT appear.
   Examples: "No oversized ring proportions, no artificial plastic-looking shine, \
              no beauty filter, no visible background seams"
             "No text overlays, no added gemstones not in reference, no fish-eye distortion"

=== OUTPUT FORMAT ===
Return ONLY valid JSON — no markdown fences, no commentary:
{{"scenes": [
  {{
    "slot": "converge",
    "scene_title": "<5 words max>",
    "aesthetic_tags": ["tag1", "tag2", "tag3"],
    "fields": {{
      "format_medium": "...",
      "subject": "...",
      "camera_framing": "...",
      "scene_setting": "...",
      "micro_details": "...",
      "product_action": "...",
      "lighting": "...",
      "negative_cues": "..."
    }}
  }},
  {{
    "slot": "explore",
    "scene_title": "...",
    "aesthetic_tags": [...],
    "fields": {{ ... }}
  }},
  {{
    "slot": "wildcard",
    "scene_title": "...",
    "aesthetic_tags": [...],
    "fields": {{ ... }}
  }}
]}}

aesthetic_tags: 3 to 6 single-word or hyphenated descriptors (e.g. "nocturnal", \
"tungsten", "brutalist", "golden-hour", "wabi-sabi").
Each field value should be 1 to 3 sentences — specific, visual, immediately actionable.
"""


def _build_meta_prompt(creative_context: dict, category: str | None, round_number: int) -> str:
    structural = creative_context.get("structural", {})
    corrections = creative_context.get("corrections", [])
    scene_history = creative_context.get("scene_history", [])
    liked_tags = creative_context.get("liked_tags", [])
    disliked_tags = creative_context.get("disliked_tags", [])

    model_key = structural.get("model", "")
    dominance_key = structural.get("dominance", "")

    model_constraint = _MODEL_CONSTRAINTS.get(model_key, _MODEL_CONSTRAINT_DEFAULT)
    dominance_constraint = _DOMINANCE_CONSTRAINTS.get(dominance_key, _DOMINANCE_CONSTRAINT_DEFAULT)
    category_description = _CATEGORY_DESCRIPTIONS.get(category or "", _CATEGORY_DEFAULT)

    if scene_history:
        scene_history_block = "\n".join(f"{i + 1}. {e}" for i, e in enumerate(scene_history))
    else:
        scene_history_block = "None yet — this is round 1. Maximize diversity across all three scenes."

    corrections_block = (
        "\n".join(f"- {c}" for c in corrections)
        if corrections
        else "No corrections yet — no specific elements to avoid or prefer."
    )
    liked_tags_block = ", ".join(liked_tags) if liked_tags else "None established yet."
    disliked_tags_block = ", ".join(disliked_tags) if disliked_tags else "None established yet."

    return _META_PROMPT_TEMPLATE.format(
        category_description=category_description,
        model_constraint=model_constraint,
        dominance_constraint=dominance_constraint,
        round_number=round_number,
        scene_history_block=scene_history_block,
        corrections_block=corrections_block,
        liked_tags_block=liked_tags_block,
        disliked_tags_block=disliked_tags_block,
    )


# ---------------------------------------------------------------------------
# Compile structured fields → text prompt for image generation
# ---------------------------------------------------------------------------

_FIELD_ORDER = [
    "format_medium",
    "subject",
    "camera_framing",
    "scene_setting",
    "micro_details",
    "product_action",
    "lighting",
    "negative_cues",
]


def compile_prompt_from_fields(fields: dict) -> str:
    """
    Serialize the 8-field structured scene dict into a JSON string prompt
    for the image generation API. JSON structure gives the model clearer
    per-field separation than flat text. Product fidelity is appended as
    a ninth field.
    """
    ordered = {k: fields.get(k, "").strip() for k in _FIELD_ORDER}
    ordered["product_fidelity"] = _PRODUCT_FIDELITY
    return json.dumps(ordered, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def generate_scene_briefs(
    creative_context: dict,
    category: str | None,
    round_number: int,
) -> list[dict]:
    """
    Make one text-only Gemini Flash call and return 3 scene brief dicts:
    [
      {
        "slot": "converge"|"explore"|"wildcard",
        "scene_title": str,
        "scene_brief": str,        # compiled text prompt, ready for image generation
        "aesthetic_tags": list[str],
        "fields": dict,            # raw 8-field dict, stored for feedback attribution
      },
      ...
    ]

    Retries once on JSON parse failure. Raises RuntimeError after 2 failures.
    """
    meta_prompt = _build_meta_prompt(creative_context, category, round_number)
    client = genai.Client(api_key=settings.gemini_api_key)
    last_error: Exception | None = None

    for attempt in range(2):
        try:
            response = await client.aio.models.generate_content(
                model=settings.gemini_analysis_model,  # gemini-2.5-flash, text only
                contents=[types.Part.from_text(text=meta_prompt)],
                config=types.GenerateContentConfig(
                    response_modalities=["TEXT"],
                ),
            )

            if not response.candidates:
                raise ValueError("Gemini returned no candidates")

            raw_text = ""
            for part in response.candidates[0].content.parts:
                if part.text:
                    raw_text += part.text

            raw_text = raw_text.strip()
            if raw_text.startswith("```"):
                raw_text = raw_text.split("```")[1]
                if raw_text.startswith("json"):
                    raw_text = raw_text[4:]
                raw_text = raw_text.strip()

            data = json.loads(raw_text)
            scenes = data.get("scenes", [])

            if len(scenes) != 3:
                raise ValueError(f"Expected 3 scenes, got {len(scenes)}")

            validated = []
            for scene in scenes:
                fields = scene.get("fields")
                if not isinstance(fields, dict):
                    raise ValueError(f"Missing fields dict for slot '{scene.get('slot')}'")

                # Verify all 8 keys present and non-empty
                missing = [k for k in _FIELD_ORDER if not fields.get(k, "").strip()]
                if missing:
                    raise ValueError(f"Scene '{scene.get('slot')}' missing fields: {missing}")

                scene_brief = compile_prompt_from_fields(fields)
                validated.append({
                    "slot": scene.get("slot", "unknown"),
                    "scene_title": scene.get("scene_title", "Untitled"),
                    "scene_brief": scene_brief,
                    "aesthetic_tags": scene.get("aesthetic_tags", []),
                    "fields": fields,
                })

            logger.info(
                "creative_director round=%d slots=%s titles=%s",
                round_number,
                [s["slot"] for s in validated],
                [s["scene_title"] for s in validated],
            )
            return validated

        except (json.JSONDecodeError, ValueError, KeyError) as exc:
            last_error = exc
            logger.warning(
                "creative_director parse failed attempt=%d/2: %s", attempt + 1, exc
            )
        except Exception as exc:
            logger.error("creative_director fatal error: %s", exc)
            raise

    raise RuntimeError(f"Creative director failed after 2 attempts: {last_error}")
