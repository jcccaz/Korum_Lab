from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import os
import httpx
from dotenv import load_dotenv

load_dotenv()

from korum_lab.extractor import (
    classify_red_team_findings,
    extract_structured_data,
    generate_escalation_reasons,
    run_adversarial_rebuttal,
    run_governor_resolution,
    run_blueprint_generation,
)
from korum_lab.models.strategy import Strategy
from korum_lab.graph.driver import GraphConnection
from korum_lab.graph.schema import setup_database
from korum_lab.graph.loaders import insert_extracted_decision, insert_concept_lock, insert_blueprint_preview
from korum_lab.graph.queries import (
    query_list_decisions,
    query_decision_by_id,
    query_concept_lock,
    query_preview_for_lock,
)

app = FastAPI(title="Korum Decision Engine API")

# Allow the Vite frontend to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class GovernanceConditions(BaseModel):
    """Kept as distinct subfields, not flattened — each answers a different
    question for a different downstream consumer:
      decision_conditions      -> What must be true to approve this?     (approval gate)
      required_validations     -> What must be checked before execution? (Foundry Build, pre-execution gate)
      failure_triggers         -> What would force reversal or review?   (Foundry Build, reversal hook)
      monitoring_requirements  -> What must be watched on an ongoing basis? (Watchtower hook)

    Shared by /api/concept-lock's response and /api/push-to-anchor's request
    — defined once, up top, so every
    downstream consumer of a Concept Lock sees the same shape.
    """
    decision_conditions: List[str] = []
    required_validations: List[str] = []
    failure_triggers: List[str] = []
    monitoring_requirements: List[str] = []


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


def _fallback_escalation_reasons(data_dict: dict) -> List[str]:
    """Content-aware fallback when escalation LLM analysis is unavailable."""
    recommendation = str(data_dict.get("recommendation") or "this recommendation").strip()
    reasons = []
    for unknown in data_dict.get("unknowns", []) or []:
        unknown = str(unknown).strip()
        if unknown:
            reasons.append(
                f"Resolve the open unknown '{unknown}' before acting on the recommendation: {recommendation}."
            )
        if len(reasons) >= 2:
            return reasons

    for risk in data_dict.get("risks", []) or []:
        risk = str(risk).strip()
        if risk:
            reasons.append(
                f"Define a control for the identified risk '{risk}' before acting on the recommendation: {recommendation}."
            )
        if len(reasons) >= 2:
            return reasons

    return reasons


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
                try:
                    escalation_reasons = generate_escalation_reasons(
                        decision_context=data_dict["decision_context"],
                        recommendation=data_dict["recommendation"],
                        evidence=evidence_list,
                        missing_evidence_types=missing,
                        decision_type=strategy.decision_type,
                        assumptions=assumptions_list,
                        risks=data_dict.get("risks", []),
                        unknowns=unknowns_list,
                    )
                except Exception:
                    # Never let an LLM hiccup block extraction. Fall back to
                    # the decision's own risks/unknowns instead of replaying
                    # generic strategy checklist labels as escalation triggers.
                    escalation_reasons = _fallback_escalation_reasons(data_dict)

                if escalation_reasons:
                    score -= 25
                    governance_reason.extend(escalation_reasons)

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
            status = "LOW CONFIDENCE — EVIDENCE GAP"
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
        decision_id = None
        try:
            with GraphConnection.get_session() as session:
                setup_database(session)
                decision_id = session.execute_write(
                    insert_extracted_decision, extracted, req.strategy, score, status
                )
            graph_status = "Injected into Neo4j Ontology"
        except Exception as e:
            graph_status = f"Offline / Bypass active (Neo4j not reachable: {str(e)})"

        data_dict["graph_injection_status"] = graph_status
        # Lets the frontend reload this exact record from history later, and
        # lets a follow-up "Send to Anchor" push reference its source decision.
        data_dict["decision_id"] = decision_id

        return data_dict

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# History — every /api/extract call is already written into Neo4j as a
# Decision node. These two endpoints just read that back, so past prompts
# (lost on refresh because the UI only held them in memory) are recoverable.
# ---------------------------------------------------------------------------

@app.get("/api/decisions")
async def list_decisions(limit: int = 50):
    try:
        with GraphConnection.get_session() as session:
            return session.execute_read(query_list_decisions, limit)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Neo4j not reachable: {str(e)}")


@app.get("/api/decisions/{decision_id}")
async def get_decision(decision_id: str):
    try:
        with GraphConnection.get_session() as session:
            record = session.execute_read(query_decision_by_id, decision_id)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Neo4j not reachable: {str(e)}")

    if record is None:
        raise HTTPException(status_code=404, detail=f"Decision {decision_id} not found")
    return record


# ---------------------------------------------------------------------------
# Concept Lock — per the KORUM Concept Lock Workflow, the goal is not to
# store decisions; it's to freeze the *reasoning that produced an approved
# architecture* into a reusable institutional pattern. A Concept Lock is
# created once Council (the Governor step) reaches a stable verdict, and is
# what gets sent to ANCHOR — not the raw decision dump.
# ---------------------------------------------------------------------------

class ConceptLockRequest(BaseModel):
    project: str
    decision_context: str
    recommendation: str
    assumptions: List[str]
    risks: List[str]
    unknowns: List[str]
    final_decision: str                            # GO / NO-GO / CONDITIONAL
    confidence_score: int
    governor_rationale: str
    new_risks_identified: Optional[List[str]] = []  # Red Team's net-new risks, folded into Risks
    decision_conditions: Optional[List[str]] = []
    required_validations: Optional[List[str]] = []
    failure_triggers: Optional[List[str]] = []
    monitoring_requirements: Optional[List[str]] = []
    decision_id: Optional[str] = None               # Neo4j Decision.id this lock freezes


@app.post("/api/concept-lock")
async def lock_concept(req: ConceptLockRequest):
    """
    Freezes a Council-approved decision into a Concept Lock — Core Thesis,
    Supporting Assumptions, Risks, Recommendations, Open Unknowns, and
    Governance Conditions. Refuses to lock a NO-GO: a rejected decision
    isn't a reusable pattern, it's a dead end, and shouldn't be archived
    as institutional memory the same way an approved one is.

    Governance Conditions stay split into four subfields rather than one
    flat list — they answer different questions for different downstream
    consumers: decision_conditions gate approval, required_validations gate
    execution (Foundry Build), failure_triggers force reversal/review, and
    monitoring_requirements are ongoing Watchtower hooks. Flattening them
    would erase that distinction.
    """
    if req.final_decision == "NO-GO":
        raise HTTPException(
            status_code=400,
            detail="Cannot lock a NO-GO decision — Concept Locks capture approved patterns only.",
        )

    core_thesis = f"{req.project}: {req.decision_context} — {req.recommendation}"
    # Council's Red Team can surface risks the original extraction missed;
    # a Concept Lock should reflect what was actually weighed, not just
    # what the first pass caught.
    all_risks = list(dict.fromkeys(req.risks + (req.new_risks_identified or [])))
    decision_conditions = req.decision_conditions or []
    required_validations = req.required_validations or []
    failure_triggers = req.failure_triggers or []
    monitoring_requirements = req.monitoring_requirements or []
    status = "LOCKED" if req.final_decision == "GO" else "CONDITIONAL_LOCK"

    lock_id = None
    try:
        with GraphConnection.get_session() as session:
            lock_id = session.execute_write(
                insert_concept_lock,
                req.decision_id,
                core_thesis,
                req.assumptions,
                all_risks,
                [req.recommendation],
                req.unknowns,
                decision_conditions,
                required_validations,
                failure_triggers,
                monitoring_requirements,
                status,
            )
        graph_status = "Locked into Neo4j Ontology"
    except Exception as e:
        graph_status = f"Offline / Bypass active (Neo4j not reachable: {str(e)})"

    return {
        "id": lock_id,
        "decision_id": req.decision_id,
        "status": status,
        "core_thesis": core_thesis,
        "supporting_assumptions": req.assumptions,
        "risks": all_risks,
        "recommendations": [req.recommendation],
        "open_unknowns": req.unknowns,
        "governance_conditions": {
            "decision_conditions": decision_conditions,
            "required_validations": required_validations,
            "failure_triggers": failure_triggers,
            "monitoring_requirements": monitoring_requirements,
        },
        "graph_status": graph_status,
    }


@app.get("/api/concept-lock/{lock_id}")
async def get_concept_lock(lock_id: str):
    try:
        with GraphConnection.get_session() as session:
            record = session.execute_read(query_concept_lock, lock_id)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Neo4j not reachable: {str(e)}")

    if record is None:
        raise HTTPException(status_code=404, detail=f"Concept Lock {lock_id} not found")

    # Reassemble the four flat Neo4j properties into the nested shape clients expect.
    return {
        "id": record["id"],
        "decision_id": record["decision_id"],
        "status": record["status"],
        "core_thesis": record["core_thesis"],
        "supporting_assumptions": record["supporting_assumptions"] or [],
        "risks": record["risks"] or [],
        "recommendations": record["recommendations"] or [],
        "open_unknowns": record["open_unknowns"] or [],
        "governance_conditions": {
            "decision_conditions": record["decision_conditions"] or [],
            "required_validations": record["required_validations"] or [],
            "failure_triggers": record["failure_triggers"] or [],
            "monitoring_requirements": record["monitoring_requirements"] or [],
        },
        "locked_at": record["locked_at"],
    }


# ---------------------------------------------------------------------------
# Concept Lock Preview Blueprint — test harness only, not Foundry's real Forge.
# ---------------------------------------------------------------------------

PREVIEW_BLUEPRINT_NOTE = (
    "Test harness preview — not the canonical Forge build. Foundry's real Forge "
    "produces the Implementation Blueprint."
)


def _list_block(values: List[str]) -> str:
    return "\n".join(f"  - {value}" for value in (values or [])) or "  None."


def _build_preview_summary(lock: dict) -> str:
    """Renders the latest Concept Lock graph record for the preview generator."""
    return f"""Concept Lock ID: {lock["id"]}
Status: {lock["status"]}

CORE THESIS
{lock["core_thesis"]}

SUPPORTING ASSUMPTIONS
{_list_block(lock.get("supporting_assumptions"))}

RISKS
{_list_block(lock.get("risks"))}

RECOMMENDATIONS
{_list_block(lock.get("recommendations"))}

OPEN UNKNOWNS
{_list_block(lock.get("open_unknowns"))}

GOVERNANCE CONDITIONS — Decision Conditions (must be true to approve)
{_list_block(lock.get("decision_conditions"))}

GOVERNANCE CONDITIONS — Required Validations (must be checked before execution)
{_list_block(lock.get("required_validations"))}

GOVERNANCE CONDITIONS — Failure Triggers (would force reversal or review)
{_list_block(lock.get("failure_triggers"))}

GOVERNANCE CONDITIONS — Monitoring Requirements (Watchtower hooks)
{_list_block(lock.get("monitoring_requirements"))}"""


def _preview_response(lock_id: str, blueprint_id: str, blueprint, graph_status: str) -> dict:
    return {
        "id": blueprint_id,
        "lock_id": lock_id,
        "status": "PREVIEW",
        "is_preview": True,
        "note": PREVIEW_BLUEPRINT_NOTE,
        "product_brief": blueprint.product_brief,
        "architecture_blueprint": blueprint.architecture_blueprint,
        "data_model": blueprint.data_model,
        "required_components": blueprint.required_components,
        "dependencies": blueprint.dependencies,
        "build_phases": blueprint.build_phases,
        "validation_gates": blueprint.validation_gates,
        "graph_status": graph_status,
    }


def _preview_record_response(lock_id: str, record: dict, graph_status: str) -> dict:
    return {
        "id": record["id"],
        "lock_id": lock_id,
        "status": "PREVIEW",
        "is_preview": True,
        "note": PREVIEW_BLUEPRINT_NOTE,
        "product_brief": record["product_brief"],
        "architecture_blueprint": record["architecture_blueprint"],
        "data_model": record["data_model"] or [],
        "required_components": record["required_components"] or [],
        "dependencies": record["dependencies"] or [],
        "build_phases": record["build_phases"] or [],
        "validation_gates": record["validation_gates"] or [],
        "graph_status": graph_status,
    }


@app.post("/api/concept-lock/{lock_id}/preview-blueprint")
async def generate_preview_blueprint(lock_id: str):
    try:
        with GraphConnection.get_session() as session:
            lock = session.execute_read(query_concept_lock, lock_id)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Neo4j not reachable: {str(e)}")

    if lock is None:
        raise HTTPException(status_code=404, detail=f"Concept Lock {lock_id} not found")

    try:
        blueprint = run_blueprint_generation(_build_preview_summary(lock))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Blueprint generation failed: {str(e)}")

    try:
        with GraphConnection.get_session() as session:
            blueprint_id = session.execute_write(insert_blueprint_preview, lock_id, blueprint)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Neo4j not reachable: {str(e)}")

    return _preview_response(lock_id, blueprint_id, blueprint, "Linked into Neo4j Ontology")


@app.get("/api/concept-lock/{lock_id}/preview-blueprint")
async def get_preview_blueprint(lock_id: str):
    try:
        with GraphConnection.get_session() as session:
            record = session.execute_read(query_preview_for_lock, lock_id)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Neo4j not reachable: {str(e)}")

    if record is None:
        raise HTTPException(status_code=404, detail=f"Blueprint Preview for Concept Lock {lock_id} not found")

    return _preview_record_response(lock_id, record, "Loaded from Neo4j")


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


def _fallback_risk_classification(original_summary: str, red_team_attack: str) -> dict:
    """Deterministic safety net if the classifier LLM is unavailable."""
    combined = f"{original_summary}\n{red_team_attack}".lower()
    finding = " ".join(red_team_attack.split())[:500] or "Red Team finding requires review"
    blocker_terms = [
        "sensitive data exposure",
        "pii",
        "api key",
        "customer data",
        "personal data",
        "credential",
        "secret",
        "external access",
        "privilege escalation",
        "cross-tenant",
        "regulatory violation",
        "legal violation",
        "missing required control",
        "missing control",
    ]
    monitoring_terms = [
        "performance",
        "storage",
        "latency",
        "collection size",
        "search latency",
    ]
    generic_condition_terms = [
        "rbac",
        "security",
        "privacy",
        "scale",
        "may not be enough",
        "might not be enough",
    ]

    if any(term in combined for term in blocker_terms):
        category = "BLOCKING RISK"
        evidence = "Red Team finding names a specific blocker category that requires proof before proceeding."
        condition = ""
    elif any(term in combined for term in monitoring_terms):
        category = "MONITORING REQUIREMENT"
        evidence = ""
        condition = "Monitor collection size/search latency for 30 days."
    elif any(term in combined for term in generic_condition_terms):
        category = "IMPLEMENTATION CONDITION"
        evidence = ""
        if "rbac" in combined and "foundry_builds" in combined:
            condition = "Verify existing RBAC applies to foundry_builds collection."
        else:
            condition = "Validate the named control path before production execution."
    else:
        category = "GENERIC CAUTION"
        evidence = ""
        condition = "Track this caution during implementation review."

    return {
        "findings": [
            {
                "finding": finding,
                "category": category,
                "evidence": evidence,
                "condition": condition,
            }
        ]
    }


def _risk_classification_has_blocker(report: dict) -> bool:
    return any(
        finding.get("category") == "BLOCKING RISK" and str(finding.get("evidence") or "").strip()
        for finding in report.get("findings", [])
    )


def _risk_classification_summary(report: dict) -> str:
    lines = []
    for finding in report.get("findings", []):
        lines.append(
            "- {category}: {finding} | evidence: {evidence} | condition: {condition}".format(
                category=finding.get("category", "GENERIC CAUTION"),
                finding=finding.get("finding", ""),
                evidence=finding.get("evidence", "") or "none",
                condition=finding.get("condition", "") or "none",
            )
        )
    return "\n".join(lines)


def _conditions_from_risk_classification(report: dict) -> List[str]:
    conditions = []
    for finding in report.get("findings", []):
        if finding.get("category") == "IMPLEMENTATION CONDITION":
            condition = str(finding.get("condition") or "").strip()
            if condition and condition not in conditions:
                conditions.append(condition)
    return conditions


def _monitoring_from_risk_classification(report: dict) -> List[str]:
    requirements = []
    for finding in report.get("findings", []):
        if finding.get("category") == "MONITORING REQUIREMENT":
            condition = str(finding.get("condition") or "").strip()
            if condition and condition not in requirements:
                requirements.append(condition)
    return requirements


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

        try:
            risk_classification = classify_red_team_findings(
                req.original_summary,
                req.red_team_attack,
            ).model_dump()
        except Exception:
            risk_classification = _fallback_risk_classification(
                req.original_summary,
                req.red_team_attack,
            )
            rule_flags.append("Risk classifier fallback used")

        has_blocking_risk = _risk_classification_has_blocker(risk_classification)
        implementation_conditions = _conditions_from_risk_classification(risk_classification)
        monitoring_requirements = _monitoring_from_risk_classification(risk_classification)

        # ── STEP 2: Model Resolution (LLM arbitration) ────────────────────────
        verdict = run_governor_resolution(
            req.original_summary,
            req.red_team_attack,
            _risk_classification_summary(risk_classification),
        )
        data = verdict.model_dump()
        data["risk_classification"] = risk_classification

        for condition in implementation_conditions:
            if condition not in data["required_validations"]:
                data["required_validations"].append(condition)
            if condition not in data["decision_conditions"]:
                data["decision_conditions"].append(condition)
        for requirement in monitoring_requirements:
            if requirement not in data["monitoring_requirements"]:
                data["monitoring_requirements"].append(requirement)

        # ── STEP 3: Final Enforcement (hard caps / overrides) ─────────────────
        # Hard floor: if confidence is critically low, block only with an
        # evidenced blocking risk; otherwise require conditional validation.
        if data["confidence_score"] < 30:
            if has_blocking_risk:
                data["final_decision"] = "NO-GO"
                data["critical_unresolved_risks"].append(
                    "Confidence below minimum execution threshold (30) with evidenced blocking risk — proceed is blocked"
                )
            else:
                data["final_decision"] = "CONDITIONAL"
                data["required_validations"].append(
                    "Confidence below minimum execution threshold (30) — validate implementation controls before execution"
                )

        # Confidence cap: Red Team REJECT + unresolved risks → cap at 60
        red_team_rejected = "REJECT" in req.red_team_attack.upper()
        has_unresolved = bool(data.get("critical_unresolved_risks")) and has_blocking_risk
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

        # NO-GO is reserved for evidenced blocking risks. Generic security,
        # scale, privacy, or performance cautions become implementation
        # conditions when a reasonable control path exists.
        if data["final_decision"] == "NO-GO" and not has_blocking_risk:
            data["final_decision"] = "CONDITIONAL"
            for risk in data.get("critical_unresolved_risks", []):
                validation = f"Validate before execution: {risk}"
                if validation not in data["required_validations"]:
                    data["required_validations"].append(validation)
            data["critical_unresolved_risks"] = []
            has_unresolved = False
            rule_flags.append(
                "Overridden NO-GO → CONDITIONAL: no evidenced BLOCKING RISK in pre-Governor classification"
            )

        # Enforce: CONDITIONAL must always have required_validations
        if data["final_decision"] == "CONDITIONAL" and not data["required_validations"]:
            data["required_validations"].append(
                "No specific validations returned — manual review required before execution"
            )

        # Hard fallback: final_decision must ALWAYS be set — never leave it empty
        if data.get("final_decision") not in ("GO", "NO-GO", "CONDITIONAL"):
            data["final_decision"] = "NO-GO" if has_blocking_risk else "CONDITIONAL"
            rule_flags.append(f"Hard fallback enforced: Governor returned no valid verdict — defaulted to {data['final_decision']}")

        # Decision status lifecycle (human-readable, maps to final_decision + context)
        has_unresolved = bool(data.get("critical_unresolved_risks")) and has_blocking_risk
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


# ---------------------------------------------------------------------------
# Send to ANCHOR — write a Concept Lock into ANCHOR's institutional memory via
# its service-to-service /api/anchor/ingest endpoint. Per the KORUM Concept
# Lock Workflow, ANCHOR is the permanent memory layer for *approved patterns*,
# not raw decisions — so this takes a locked Concept Lock (Core Thesis,
# Supporting Assumptions, Risks, Recommendations, Open Unknowns, Governance
# Conditions), not the original extraction. Lock it first via /api/concept-lock.
# ---------------------------------------------------------------------------

class PushToAnchorRequest(BaseModel):
    project: str
    core_thesis: str
    supporting_assumptions: List[str]
    risks: List[str]
    recommendations: List[str]
    open_unknowns: List[str]
    governance_conditions: GovernanceConditions
    status: str                                    # LOCKED / CONDITIONAL_LOCK
    lock_id: Optional[str] = None                   # ConceptLock.id, for dedup/correlation
    decision_id: Optional[str] = None               # Source Decision.id, for traceability


def _build_anchor_package(req: PushToAnchorRequest) -> str:
    """Renders the Concept Lock as a clean markdown knowledge record for ANCHOR's archive."""
    assumptions_block = "\n".join(f"  - {a}" for a in req.supporting_assumptions) or "  None."
    risks_block = "\n".join(f"  - {r}" for r in req.risks) or "  None."
    recommendations_block = "\n".join(f"  - {r}" for r in req.recommendations) or "  None."
    unknowns_block = "\n".join(f"  - {u}" for u in req.open_unknowns) or "  None."

    gc = req.governance_conditions
    decision_conditions_block = "\n".join(f"  - {c}" for c in gc.decision_conditions) or "  None."
    required_validations_block = "\n".join(f"  - {v}" for v in gc.required_validations) or "  None."
    failure_triggers_block = "\n".join(f"  - {t}" for t in gc.failure_triggers) or "  None."
    monitoring_requirements_block = "\n".join(f"  - {m}" for m in gc.monitoring_requirements) or "  None."

    return f"""# CONCEPT LOCK ({req.status}): {req.project}

### CORE THESIS
{req.core_thesis}

### SUPPORTING ASSUMPTIONS
{assumptions_block}

### RISKS
{risks_block}

### RECOMMENDATIONS
{recommendations_block}

### OPEN UNKNOWNS
{unknowns_block}

### GOVERNANCE CONDITIONS

**Decision Conditions** (what must be true to approve this)
{decision_conditions_block}

**Required Validations** (what must be checked before execution)
{required_validations_block}

**Failure Triggers** (what would force reversal or review)
{failure_triggers_block}

**Monitoring Requirements** (what Watchtower must keep watching)
{monitoring_requirements_block}"""


@app.post("/api/push-to-anchor")
async def push_to_anchor(req: PushToAnchorRequest):
    """
    Archive a Concept Lock into ANCHOR's institutional memory so it's
    searchable later — "Have we done this before? What assumptions
    supported it? What risks were accepted?" Separate from Push-to-KorumOS,
    which hands a decision to another council for execution planning.

    Requires ANCHOR_URL and ANCHOR_API_KEY in environment (the same Bearer key
    configured as ANCHOR_API_KEY on the anchor-runtime server). If the key isn't
    set, returns the formatted package so the operator can ingest it manually.
    """
    anchor_url = os.getenv("ANCHOR_URL", "").rstrip("/")
    anchor_api_key = os.getenv("ANCHOR_API_KEY", "").strip()
    package = _build_anchor_package(req)

    # --- Fallback: no API key configured — return the package for manual use ---
    if not anchor_api_key:
        return {
            "status": "manual_required",
            "message": "ANCHOR_API_KEY not configured. Copy the package below into ANCHOR.",
            "query_package": package,
            "anchor_url": anchor_url or None,
        }

    if not anchor_url:
        raise HTTPException(status_code=500, detail="ANCHOR_URL not configured.")

    payload = {
        "content": package,
        "source": "korum",
        "entry_type": "concept_lock",
        "collection": "korum_decisions",  # Concept Locks are the institutional-memory artifact KORUM contributes to ANCHOR.
        "title": f"Concept Lock: {req.project}",
        "project_id": req.project,
        "mission_id": req.lock_id,
        "metadata": {
            "status": req.status,
            "decision_id": req.decision_id,
        },
    }

    headers = {
        "Authorization": f"Bearer {anchor_api_key}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{anchor_url}/api/anchor/ingest",
                json=payload,
                headers=headers,
            )

        if response.status_code == 200:
            data = response.json()
            return {
                "status": data.get("status", "submitted"),
                "anchor_response": data,
                "query_package": package,
            }
        else:
            return {
                "status": "error",
                "http_status": response.status_code,
                "detail": response.text,
                "query_package": package,  # Always return the package so work isn't lost
            }

    except httpx.TimeoutException:
        raise HTTPException(
            status_code=504,
            detail="ANCHOR did not respond within 30 seconds. The package is returned — ingest manually if needed.",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
