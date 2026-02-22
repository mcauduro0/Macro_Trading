"""Narrative generation package.

Exports:
    NarrativeGenerator -- Claude API / template-fallback narrative builder.
    NarrativeBrief     -- Dataclass for generated narrative output.
    render_template    -- Standalone template-based fallback renderer.
"""

from src.narrative.generator import NarrativeBrief, NarrativeGenerator
from src.narrative.templates import render_template

__all__ = ["NarrativeGenerator", "NarrativeBrief", "render_template"]
