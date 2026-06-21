from pydantic import BaseModel, Field
from typing import List


class EscalationAnalysis(BaseModel):
    reasons: List[str] = Field(
        description="One natural sentence per missing evidence type, explaining "
        "specifically why THIS decision needs that evidence — reference the "
        "decision's actual content (project, context, recommendation), not a "
        "generic restatement of the evidence category name."
    )
