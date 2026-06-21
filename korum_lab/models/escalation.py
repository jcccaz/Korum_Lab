from pydantic import BaseModel, Field
from typing import List


class EscalationAnalysis(BaseModel):
    reasons: List[str] = Field(
        description="Zero or more natural escalation sentences. Include a "
        "reason only when a candidate missing evidence category is materially "
        "relevant to THIS decision. Reference the actual decision content, "
        "risks, unknowns, or recommendation; do not restate or paraphrase the "
        "generic evidence category name."
    )
