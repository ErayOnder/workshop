from dataclasses import dataclass


BASE_PROMPT = (
    "High-end luxury product photography of the exact same ring shown in the reference image. "
    "Pristine white marble surface, soft diffused studio lighting, subtle specular reflections. "
    "Ultra-sharp 8K macro photography, commercial jewelry advertisement quality. "
    "Preserve identical ring design, metal color, and gemstone exactly as in the reference. "
)


@dataclass
class Angle:
    key: str
    label: str
    suffix: str


ANGLES: list[Angle] = [
    Angle(
        key="front",
        label="Front Face",
        suffix="Camera directly facing the ring, ring standing upright, perfect front symmetry.",
    ),
    Angle(
        key="three_quarter",
        label="3/4 View",
        suffix="Camera at 45-degree angle elevated slightly, showing face and band depth.",
    ),
    Angle(
        key="side_profile",
        label="Side Profile",
        suffix="Camera at exact 90-degree side, showing full band width and thickness.",
    ),
    Angle(
        key="overhead",
        label="Overhead",
        suffix="Camera directly overhead looking straight down, ring lying flat on the surface.",
    ),
    Angle(
        key="macro_detail",
        label="Macro Detail",
        suffix="Extreme close-up macro, camera tilted 30 degrees, showcasing stone facets and setting detail.",
    ),
    Angle(
        key="low_hero",
        label="Hero Low Angle",
        suffix="Camera at very low angle near surface, shooting upward through ring opening, dramatic cinematic perspective.",
    ),
]
