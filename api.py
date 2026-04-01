from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import os
from dotenv import load_dotenv

load_dotenv()

from korum_lab.extractor import extract_structured_data
from korum_lab.models.strategy import Strategy
from korum_lab.graph.driver import GraphConnection
from korum_lab.graph.schema import setup_database
from korum_lab.graph.loaders import insert_extracted_decision

app = FastAPI(title="Korum Decision Engine API")

# Allow the Vite frontend to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ExtractRequest(BaseModel):
    text: str
    strategy: Optional[Strategy] = None


def _check_required_evidence(evidence_list: List[str], required_phrases: List[str]) -> List[str]:
    """Returns required evidence types that are absent from extracted evidence."""
    stopwords = {"the", "and", "for", "that", "this", "with", "from", "or", "a", "an"}
    evidence_text = " ".join(evidence_list).lower()
    missing = []
    for phrase in required_phrases:
        keywords = [w for w in phrase.lower().split() if len(w) > 3 and w not in stopwords]
        if not any(kw in evidence_text for kw in keywords):
            missing.append(phrase)
    return missing


@app.post("/api/extract")
async def extract_decision(req: ExtractRequest):
    if not os.environ.get("OPENAI_API_KEY"):
        raise HTTPException(
            status_code=500,
            detail="OPENAI_API_KEY environment variable is not set. Cannot run extraction.",
        )

    try:
        # STEP 1: Neural Extraction
        extracted = extract_structured_data(req.text)
        data_dict = extracted.model_dump()

        # STEP 2: Strategy-Aware Governor & Confidence Scoring
        evidence_list = data_dict.get("evidence", [])
        unknowns_list = data_dict.get("unknowns", [])
        assumptions_list = data_dict.get("assumptions", [])

        evidence_weight = len(evidence_list) * 15
        penalties = (len(assumptions_list) * 10) + (len(unknowns_list) * 15)
        score = 80 + evidence_weight - penalties

        governance_reason: List[str] = []
        strategy_applied = None

        if req.strategy:
            strategy = req.strategy
            strategy_applied = {
                "decision_type": strategy.decision_type,
                "objective": strategy.objective,
            }

            # Penalty: missing required evidence
            missing = _check_required_evidence(evidence_list, strategy.required_evidence)
            if missing:
                score -= 25
                for m in missing:
                    governance_reason.append(f"Missing required evidence: {m}")

            # Penalty: unknowns exceed evidence
            if len(unknowns_list) > len(evidence_list):
                score -= 20
                governance_reason.append(
                    f"Unknown count ({len(unknowns_list)}) exceeds evidence count ({len(evidence_list)}) "
                    f"— unacceptable uncertainty for {strategy.decision_type}"
                )

        score = max(20, min(99, score))
        data_dict["confidence_score"] = score

        # Base governance status
        if score >= 80:
            status = "NEURAL COUNCIL APPROVED"
            color = "success"
        elif score >= 50:
            status = "HUMAN REVIEW REQUIRED"
            color = "warning"
        else:
            status = "CONTESTED BY RED TEAM"
            color = "danger"

        # Strategy overrides: enforce escalation rules
        if req.strategy:
            threshold = req.strategy.escalation_rules.get("confidence_below", 65)
            if score < threshold and status == "NEURAL COUNCIL APPROVED":
                status = "HUMAN REVIEW REQUIRED"
                color = "warning"
                governance_reason.append(
                    f"Confidence {score} is below strategy escalation threshold ({threshold})"
                )
            # Prevent APPROVED if any strategy constraint triggered
            if governance_reason and status == "NEURAL COUNCIL APPROVED":
                status = "HUMAN REVIEW REQUIRED"
                color = "warning"

        data_dict["governance_status"] = status
        data_dict["status_color"] = color
        data_dict["governance_reason"] = governance_reason
        data_dict["strategy_applied"] = strategy_applied

        # STEP 3: Graph Ontology Injection (Fail-safe for live demos without Docker running)
        graph_status = "Skipped"
        try:
            driver = GraphConnection.get_driver()
            with driver.session() as session:
                setup_database(session)
                session.execute_write(insert_extracted_decision, extracted, req.strategy)
            graph_status = "Injected into Neo4j Ontology"
        except Exception as e:
            graph_status = f"Offline / Bypass active (Neo4j not reachable: {str(e)})"

        data_dict["graph_injection_status"] = graph_status

        return data_dict

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
