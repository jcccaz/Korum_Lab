from pydantic import BaseModel
from typing import List, Dict, Any


class Strategy(BaseModel):
    objective: str
    decision_type: str
    success_criteria: List[str] = []
    required_evidence: List[str] = []
    risk_tolerance: str
    time_horizon: str
    escalation_rules: Dict[str, Any] = {}


STRATEGY_PRESETS: Dict[str, Strategy] = {
    "Incident Response": Strategy(
        objective="Maintain service stability while minimizing customer impact",
        decision_type="Incident Response",
        success_criteria=[
            "Restore stability quickly",
            "Avoid cascading failures",
        ],
        required_evidence=[
            "Telemetry or log confirmation",
            "Operational or field confirmation",
        ],
        risk_tolerance="Medium",
        time_horizon="Immediate",
        escalation_rules={
            "confidence_below": 65,
            "unknowns_exceed_evidence": True,
            "missing_required_evidence": True,
        },
    ),
    "Financial Review": Strategy(
        objective="Validate financial decision against risk exposure and return thresholds",
        decision_type="Financial Review",
        success_criteria=[
            "ROI clearly demonstrated",
            "Risk exposure within approved limits",
        ],
        required_evidence=[
            "Financial data or projections",
            "Risk assessment or audit trail",
        ],
        risk_tolerance="Low",
        time_horizon="Short-term",
        escalation_rules={
            "confidence_below": 70,
            "unknowns_exceed_evidence": True,
            "missing_required_evidence": True,
        },
    ),
    "Strategic Planning": Strategy(
        objective="Align decision with long-term organizational objectives and market position",
        decision_type="Strategic Planning",
        success_criteria=[
            "Aligns with stated mission",
            "Competitive advantage demonstrated",
        ],
        required_evidence=[
            "Market or competitive analysis",
            "Stakeholder or leadership input",
        ],
        risk_tolerance="High",
        time_horizon="Long-term",
        escalation_rules={
            "confidence_below": 55,
            "unknowns_exceed_evidence": False,
            "missing_required_evidence": True,
        },
    ),
}
