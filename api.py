from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import os
import httpx
from dotenv import load_dotenv

load_dotenv()

from korum_lab.extractor import extract_structured_data, run_adversarial_rebuttal, run_governor_resolution
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
    rebuttal_text: Optional[str] = None
    previous_score: Optional[int] = None

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "Korum Decision Engine API"}



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
        # If a rebuttal is provided, combine it with the original context
        combined_text = req.text
        if req.rebuttal_text and req.rebuttal_text.strip():
            combined_text = (
                f"{req.text}\n\n"
                f"[REBUTTAL / ADDITIONAL CONTEXT]\n"
                f"{req.rebuttal_text.strip()}"
            )

        extracted = extract_structured_data(combined_text)
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
        data_dict["rebuttal_applied"] = bool(req.rebuttal_text and req.rebuttal_text.strip())
        data_dict["score_delta"] = (score - req.previous_score) if req.previous_score is not None else None

        # STEP 3: Graph Ontology Injection (Fail-safe for live demos without Docker running)
        graph_status = "Skipped"
        try:
            with GraphConnection.get_session() as session:
                setup_database(session)
                session.execute_write(insert_extracted_decision, extracted, req.strategy)
            graph_status = "Injected into Neo4j Ontology"
        except Exception as e:
            graph_status = f"Offline / Bypass active (Neo4j not reachable: {str(e)})"

        data_dict["graph_injection_status"] = graph_status

        return data_dict

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class RebuttalRequest(BaseModel):
    decision_summary: str


@app.post("/api/rebuttal")
async def adversarial_rebuttal(req: RebuttalRequest):
    """Runs the extracted decision through local Mistral 7B for adversarial challenge."""
    if not req.decision_summary.strip():
        raise HTTPException(status_code=400, detail="decision_summary is required")
    try:
        attack = run_adversarial_rebuttal(req.decision_summary)
        return {"rebuttal": attack}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class GovernorRequest(BaseModel):
    original_summary: str
    red_team_attack: str


@app.post("/api/governor")
async def governor_resolution(req: GovernorRequest):
    """
    3-Step Governor Resolution:
    Step 1 — Rule Checks (deterministic, pre-LLM)
    Step 2 — Model Resolution (GPT-4o structured arbitration)
    Step 3 — Final Enforcement (hard caps and overrides, post-LLM)
    """
    if not req.original_summary.strip():
        raise HTTPException(status_code=400, detail="original_summary is required")
    if not req.red_team_attack.strip():
        raise HTTPException(status_code=400, detail="red_team_attack is required")

    try:
        # ── STEP 1: Rule Checks (deterministic) ──────────────────────────────
        rule_flags: List[str] = []
        attack_upper = req.red_team_attack.upper()

        if "REJECT" in attack_upper:
            rule_flags.append("Red Team issued explicit REJECT verdict")
        if "NO-GO" in attack_upper:
            rule_flags.append("Red Team recommended NO-GO")
        if "CRITICAL" in attack_upper and "ASSUMPTION" in attack_upper:
            rule_flags.append("Red Team flagged a critical assumption failure")
        if "MISSING EVIDENCE" in attack_upper or "NO EVIDENCE" in attack_upper:
            rule_flags.append("Red Team cited missing or absent evidence")

        # ── STEP 2: Model Resolution (LLM arbitration) ────────────────────────
        verdict = run_governor_resolution(req.original_summary, req.red_team_attack)
        data = verdict.model_dump()

        # ── STEP 3: Final Enforcement (hard caps / overrides) ─────────────────
        # Hard floor: if LLM confidence is critically low, force NO-GO
        if data["confidence_score"] < 30:
            data["final_decision"] = "NO-GO"
            data["critical_unresolved_risks"].append(
                "Confidence below minimum execution threshold (30) — proceed is blocked"
            )

        # Confidence cap: Red Team REJECT + unresolved risks → cap at 60
        red_team_rejected = "REJECT" in req.red_team_attack.upper()
        has_unresolved = bool(data.get("critical_unresolved_risks"))
        if red_team_rejected and has_unresolved and data["confidence_score"] > 60:
            data["confidence_score"] = 60
            rule_flags.append(
                "Confidence capped at 60: Red Team issued REJECT with unresolved critical risks"
            )

        # Hard cap: if Red Team SUSTAINED + critical risks exist, cannot be GO
        if (
            data["red_team_verdict"] == "SUSTAINED"
            and has_unresolved
            and data["final_decision"] == "GO"
        ):
            data["final_decision"] = "CONDITIONAL"
            rule_flags.append(
                "Overridden GO → CONDITIONAL: Red Team sustained with unresolved critical risks"
            )

        # Enforce: CONDITIONAL must always have required_validations
        if data["final_decision"] == "CONDITIONAL" and not data["required_validations"]:
            data["required_validations"].append(
                "No specific validations returned — manual review required before execution"
            )

        # Hard fallback: final_decision must ALWAYS be set — never leave it empty
        if data.get("final_decision") not in ("GO", "NO-GO", "CONDITIONAL"):
            data["final_decision"] = "NO-GO"
            rule_flags.append("Hard fallback enforced: Governor returned no valid verdict — defaulted to NO-GO")

        # Decision status lifecycle (human-readable, maps to final_decision + context)
        fd = data["final_decision"]
        rt = data["red_team_verdict"]
        score = data["confidence_score"]
        if fd == "GO":
            decision_status = "GO"
        elif fd == "NO-GO":
            decision_status = "NO-GO"
        elif rt == "SUSTAINED" and has_unresolved:
            decision_status = "ENFORCED CONDITIONAL"
        elif score < 65:
            decision_status = "HUMAN REVIEW REQUIRED"
        else:
            decision_status = "ENFORCED CONDITIONAL"

        data["decision_status"] = decision_status
        data["rule_flags"] = rule_flags
        return data

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# STEP 4: Push to KorumOS Council
# Takes the Governor verdict and packages it as a pre-tested query for the
# full KorumOS Neural Council. The council receives a structured brief —
# evidence, unknowns, risks, and Governor ruling already resolved —
# so it can focus on execution planning rather than re-deriving the basics.
# ---------------------------------------------------------------------------

class PushToKorumRequest(BaseModel):
    project: str
    decision_context: str
    evidence: List[str]
    assumptions: List[str]
    unknowns: List[str]
    risks: List[str]
    recommendation: str
    governor_verdict: str                        # GO / NO-GO / CONDITIONAL
    governor_confidence: int                     # 0-100
    governor_rationale: str
    required_validations: Optional[List[str]] = []
    failure_triggers: Optional[List[str]] = []
    monitoring_requirements: Optional[List[str]] = []
    mission_type: Optional[str] = "STRATEGY"    # KorumOS mission type / tab
    workflow: Optional[str] = None              # Override workflow if needed


def _build_korum_query(req: PushToKorumRequest) -> str:
    """
    Constructs a pre-tested query package for the KorumOS Neural Council.
    The council inherits all pre-work — it does not re-derive the basics.
    """
    evidence_block = "\n".join(f"  - {e}" for e in req.evidence) or "  None confirmed."
    assumptions_block = "\n".join(f"  - {a}" for a in req.assumptions) or "  None."
    unknowns_block = "\n".join(f"  - {u}" for u in req.unknowns) or "  None."
    risks_block = "\n".join(f"  - {r}" for r in req.risks) or "  None."
    validations_block = "\n".join(f"  - {v}" for v in req.required_validations) or "  None."
    triggers_block = "\n".join(f"  - {t}" for t in req.failure_triggers) or "  None."
    monitoring_block = "\n".join(f"  - {m}" for m in req.monitoring_requirements) or "  None."

    return f"""## KORUM LAB PRE-ANALYSIS PACKAGE
## Project: {req.project}

This decision has been pre-processed through Korum Lab — extraction, adversarial Red Team attack, and Governor arbitration are complete. Do not re-derive what is already established. Build on this foundation.

---

### DECISION CONTEXT
{req.decision_context}

### VERIFIED EVIDENCE
{evidence_block}

### KNOWN ASSUMPTIONS (unverified)
{assumptions_block}

### CRITICAL UNKNOWNS
{unknowns_block}

### IDENTIFIED RISKS
{risks_block}

---

### PRE-TEST VERDICT: {req.governor_verdict} (Confidence: {req.governor_confidence}/100)
{req.governor_rationale}

### REQUIRED VALIDATIONS (must be resolved before execution)
{validations_block}

### FAILURE TRIGGERS (immediate invalidation events)
{triggers_block}

### MONITORING REQUIREMENTS (track during and after execution)
{monitoring_block}

---

### ORIGINAL RECOMMENDATION
{req.recommendation}

---

### COUNCIL DIRECTIVE
Run full Neural Council governance on this decision. The pre-analysis has surfaced the key risks, unknowns, and Governor ruling. Your mandate:
1. Resolve each critical unknown with a specific investigative action or assumption-flag.
2. Validate or challenge the required validations — are they sufficient to unlock execution?
3. Stress-test the failure triggers — are there additional invalidation events the pre-analysis missed?
4. Produce an executable action plan with phased steps, owners, and gating conditions.
5. Issue a final GO / NO-GO / CONDITIONAL with your own confidence score.

Do not summarize what was already provided. Add intelligence the pre-analysis did not have."""


@app.post("/api/push-to-korum")
async def push_to_korum(req: PushToKorumRequest):
    """
    Step 4: Package the Governor verdict as a pre-tested query and submit
    to the KorumOS Neural Council for full governed decision intelligence.

    Requires KORUMOS_URL and KORUMOS_API_KEY in environment.
    If KORUMOS_API_KEY is not set, returns the formatted query package
    so the operator can paste it into KorumOS manually.
    """
    korumos_url = os.getenv("KORUMOS_URL", "").rstrip("/")
    korumos_api_key = os.getenv("KORUMOS_API_KEY", "").strip()
    query = _build_korum_query(req)

    # --- Fallback: no API key configured — return the package for manual use ---
    if not korumos_api_key:
        return {
            "status": "manual_required",
            "message": "KORUMOS_API_KEY not configured. Copy the query package below into KorumOS.",
            "query_package": query,
            "korumos_url": korumos_url or "https://korum-os.com",
        }

    if not korumos_url:
        raise HTTPException(status_code=500, detail="KORUMOS_URL not configured.")

    # --- Live bridge: POST to KorumOS /api/ask ---
    payload = {
        "query": query,
        "mission_type": req.mission_type,
    }
    if req.workflow:
        payload["workflow"] = req.workflow

    headers = {
        "Authorization": f"Bearer {korumos_api_key}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{korumos_url}/api/ask",
                json=payload,
                headers=headers,
            )

        if response.status_code == 200:
            data = response.json()
            return {
                "status": "submitted",
                "job_id": data.get("job_id"),
                "poll_url": f"{korumos_url}/api/status/{data.get('job_id')}",
                "query_package": query,
                "korumos_response": data,
            }
        else:
            return {
                "status": "error",
                "http_status": response.status_code,
                "detail": response.text,
                "query_package": query,  # Always return the package so work isn't lost
            }

    except httpx.TimeoutException:
        raise HTTPException(
            status_code=504,
            detail="KorumOS did not respond within 30 seconds. The query package is returned — submit manually if needed.",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
