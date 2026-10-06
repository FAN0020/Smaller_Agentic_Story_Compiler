"""Provider-independent contracts. Creative choices are data; invariants are code."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Style(Contract):
    id: str
    name: str
    description: str
    palette: list[str]
    instruction: str


STYLES = [
    Style(
        id="watercolor",
        name="Watercolor",
        description="Luminous washes. Soft edges. Quiet wonder.",
        palette=["#e9d9b5", "#789e91", "#6d89a3"],
        instruction="Transparent watercolor washes on textured paper, soft pigment blooms, restrained natural palette, expressive hand-painted figures.",
    ),
    Style(
        id="gouache",
        name="Gouache",
        description="Velvety color with a handcrafted warmth.",
        palette=["#e5bd6b", "#bd654c", "#315b54"],
        instruction="Opaque gouache painting, matte layered brushstrokes, warm rich colors, confident shapes, subtle paper grain.",
    ),
    Style(
        id="oil-painting",
        name="Oil painting",
        description="Rich texture. Painterly light. Cinematic depth.",
        palette=["#d7af6b", "#57675c", "#393b4a"],
        instruction="Expressive oil painting, visible impasto brushwork, rich chiaroscuro, luminous pigments, consistent painted texture during motion.",
    ),
    Style(
        id="ink-wash",
        name="Ink wash",
        description="Flowing brushwork and expressive negative space.",
        palette=["#e7e3d7", "#8a9691", "#344942"],
        instruction="Traditional ink wash painting, fluid black brushwork, graded gray washes, rice-paper texture, selective muted color, generous negative space.",
    ),
    Style(
        id="impressionism",
        name="Impressionism",
        description="Broken color and fleeting, sunlit moments.",
        palette=["#dfc574", "#729794", "#a68db3"],
        instruction="Impressionist painting, visible broken brushstrokes, complementary color, natural light, atmospheric depth, stable subject silhouettes.",
    ),
    Style(
        id="graphic-novel",
        name="Graphic novel",
        description="Bold silhouettes and dramatic illustrated frames.",
        palette=["#e2b650", "#97575c", "#293b4a"],
        instruction="Graphic novel illustration, decisive ink contours, controlled halftone shading, cinematic panel composition, limited vivid palette, no text or speech bubbles.",
    ),
    Style(
        id="paper-cutout",
        name="Paper cutout",
        description="Layered paper worlds with tactile depth.",
        palette=["#e4d4ac", "#699080", "#cb785f"],
        instruction="Layered hand-cut paper illustration, tactile fibers, dimensional paper shadows, clean silhouettes, intentional stop-motion movement.",
    ),
    Style(
        id="anime",
        name="Anime painting",
        description="Expressive characters in painted worlds.",
        palette=["#e3cfa3", "#789bb0", "#ce817c"],
        instruction="Original anime-inspired hand-painted animation, clean expressive character design, richly painted backgrounds, controlled cel shading, no resemblance to existing franchises.",
    ),
]
STYLE_BY_ID = {s.id: s for s in STYLES}


class DirectorPolicy(Contract):
    hook_latency_max_seconds: int
    age_range: str | None
    pacing: str
    principles: list[str]


class CreativeBrief(Contract):
    mode: Literal["general", "children"] = "general"
    style: str = "watercolor"
    target_seconds: int = Field(default=120, ge=60, le=240, multiple_of=4)
    age_range: Literal["3–5", "6–9", "10–12"] = "6–9"
    fidelity: Literal["faithful", "balanced", "creative"] = "faithful"
    direction: str = Field(default="", max_length=2000)
    aspect: Literal["16:9", "9:16"] = "16:9"

    @field_validator("style")
    @classmethod
    def known_style(cls, value):
        if value not in STYLE_BY_ID:
            raise ValueError("Choose a supported painting style")
        return value

    @property
    def policy(self):
        if self.mode == "children":
            return DirectorPolicy(
                hook_latency_max_seconds=12,
                age_range=self.age_range,
                pacing="Clear cause and effect, moderate cuts, readable single actions, short dialogue.",
                principles=[
                    "Disclose age adaptations",
                    "No frightening embellishment",
                    "Readable reactions and emotional reassurance",
                    "Stable screen geography",
                ],
            )
        return DirectorPolicy(
            hook_latency_max_seconds=5,
            age_range=None,
            pacing="Enter late; leave on a meaningful change. Contrast tension with earned relief.",
            principles=[
                "Source-supported hooks and reversals only",
                "Track audience/character knowledge separately",
                "Pay off setups and carry open loops",
                "Show consequences and reactions",
            ],
        )


class SourceChunk(Contract):
    id: str
    text: str
    start: int
    end: int


def chunk_source(text: str, limit: int = 6000) -> list[SourceChunk]:
    if not text.strip() or limit < 100:
        raise ValueError("A non-empty story and a chunk limit of at least 100 are required")
    chunks, start = [], 0
    while start < len(text):
        end = min(start + limit, len(text))
        if end < len(text):
            boundary = text.rfind("\n\n", start + limit // 2, end)
            if boundary != -1:
                end = boundary + 2
        chunks.append(SourceChunk(id=f"src-{len(chunks) + 1:04}", text=text[start:end], start=start, end=end))
        start = end
    return chunks


def fingerprint(value: Any) -> str:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    ).hexdigest()


def select_episodes(mode: str, count: int, custom: list[int] | None = None) -> list[int]:
    if count < 1:
        raise ValueError("Plan the episode sequence first")
    if mode == "one":
        return [1]
    if mode == "five":
        return list(range(1, min(5, count) + 1))
    if mode == "all":
        return list(range(1, count + 1))
    if mode != "custom" or not custom or any(n < 1 or n > count for n in custom):
        raise ValueError(f"Choose episode numbers between 1 and {count}")
    return sorted(set(custom))
