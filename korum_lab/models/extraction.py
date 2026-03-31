from pydantic import BaseModel, Field
from typing import List

# =====================================================================
# THE KORUM ONTOLOGY SCHEMA
# This enforces the rules. Unstructured data MUST conform to this shape.
# =====================================================================
class ExtractedDecision(BaseModel):
    project: str = Field(description="The formal name of the project or initiative")
    decision_context: str = Field(description="The core decision being faced or evaluated")
    evidence: List[str] = Field(description="Hard facts or logs backing the current situation")
    assumptions: List[str] = Field(description="Beliefs held without absolute proof")
    unknowns: List[str] = Field(description="Critical pieces of missing information")
    risks: List[str] = Field(description="Potential negative consequences")
    recommendation: str = Field(description="The suggested course of action")
