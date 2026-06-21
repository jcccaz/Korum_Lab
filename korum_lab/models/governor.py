from pydantic import BaseModel, Field
from typing import List, Literal


RiskCategory = Literal[
    "CORE THESIS ATTACK",
    "BLOCKING RISK",
    "IMPLEMENTATION CONDITION",
    "MONITORING REQUIREMENT",
    "GENERIC CAUTION",
]


class ClassifiedRiskFinding(BaseModel):
    finding: str = Field(
        description="The Red Team finding being classified, written as a concise natural sentence."
    )
    category: RiskCategory = Field(
        description="Risk class used by the Governor before final arbitration."
    )
    evidence: str = Field(
        description="Specific evidence or failure mode supporting the category. Empty only for generic cautions."
    )
    condition: str = Field(
        description="Implementation condition or monitoring requirement if the finding is not a blocker."
    )


class RiskClassificationReport(BaseModel):
    findings: List[ClassifiedRiskFinding] = Field(
        description="One classified item per material Red Team finding."
    )


class GovernorVerdict(BaseModel):
    final_decision: Literal["GO", "NO-GO", "CONDITIONAL"] = Field(
        description="Final ruling after weighing primary analysis against Red Team attack"
    )
    confidence_score: int = Field(
        description="Adjusted confidence 0–100 after adversarial pressure applied"
    )
    red_team_verdict: Literal["SUSTAINED", "PARTIALLY SUSTAINED", "REJECTED"] = Field(
        description="Whether the Red Team attack introduced valid risk that changes the outcome"
    )
    new_risks_identified: List[str] = Field(
        description="Net-new risks surfaced by Red Team that were absent from the original analysis"
    )
    critical_unresolved_risks: List[str] = Field(
        description="Risks that remain unresolved and block execution"
    )
    required_validations: List[str] = Field(
        description="Specific items that must be validated before any action is taken"
    )
    decision_conditions: List[str] = Field(
        description="Must-pass conditions — if any of these are not met, the decision cannot proceed"
    )
    failure_triggers: List[str] = Field(
        description="Specific events or findings that would immediately invalidate this decision"
    )
    monitoring_requirements: List[str] = Field(
        description="What must be tracked in real time during and after execution of this decision"
    )
    governor_rationale: str = Field(
        description="One-paragraph explanation of the ruling — why this verdict, why this score"
    )
