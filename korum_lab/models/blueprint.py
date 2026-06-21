from pydantic import BaseModel, Field
from typing import List


# =====================================================================
# FORGE MVP — Build Blueprint Generator
#
# Scope (deliberately limited): this answers "How would we build this?"
# It does NOT generate code, scaffold a repo, or produce a deployment
# plan — that's the full Forge vision described in
# KorumOS/docs/FOUNDRY_FORGE_TOMORROW.md, which is intentionally out of
# scope until this narrower handoff (Concept Lock -> actionable
# implementation blueprint) is proven to work repeatedly.
# =====================================================================
class BuildBlueprint(BaseModel):
    product_brief: str = Field(
        description="One-paragraph framing of what's being built, for whom, and why — "
        "grounded in the Concept Lock's Core Thesis and Recommendations, not a generic pitch."
    )
    architecture_blueprint: str = Field(
        description="High-level technical design narrative: major pieces and how they fit "
        "together. Description, not code — no file contents, no actual implementation."
    )
    data_model: List[str] = Field(
        description="Key entities/structures this needs (e.g. 'Decision node with id, status, "
        "confidence_score'), one per line. Conceptual schema, not SQL/Cypher DDL."
    )
    required_components: List[str] = Field(
        description="Services, modules, or pieces that must exist (e.g. 'REST endpoint for X', "
        "'background worker for Y'), one per line."
    )
    dependencies: List[str] = Field(
        description="External dependencies this would need — libraries, APIs, infrastructure, "
        "other KORUM systems — one per line."
    )
    build_phases: List[str] = Field(
        description="Ordered phases to build this in, each a short actionable phrase (e.g. "
        "'Phase 1: stand up the data model and storage layer'). Sequence matters."
    )
    validation_gates: List[str] = Field(
        description="What must be checked/pass before moving to the next phase or considering "
        "this done — informed by the Concept Lock's Governance Conditions but specific to the "
        "build itself (e.g. 'Phase 1 gate: schema migration runs clean against a fresh DB')."
    )
