import hashlib
from datetime import datetime, timezone
from typing import Optional

from korum_lab.models.strategy import Strategy


def generate_id(text: str) -> str:
    """Generates a reliable hash ID based on the decision context text."""
    return hashlib.md5(text.encode('utf-8')).hexdigest()[:8]


def insert_extracted_decision(
    tx,
    data,
    strategy: Optional[Strategy] = None,
    confidence_score: Optional[int] = None,
    governance_status: Optional[str] = None,
):
    """Inserts a Pydantic 'ExtractedDecision' straight into the Neo4j graph using the Korum Ontology.

    Returns the decision_id so callers (the API layer) can correlate this graph
    record with the extraction response — needed for history lookups and for
    linking outbound pushes (e.g. to ANCHOR) back to their source decision.
    """

    # Generate unique ID for the central decision node
    decision_id = f"DEC-{generate_id(data.decision_context)}"

    # 1. Base nodes: Project & Decision
    # ON CREATE captures created_at once so history can be sorted chronologically;
    # ON MATCH only refreshes the fields that may change on re-extraction (e.g. a
    # rebuttal re-run improving the confidence score), without clobbering created_at.
    query = """
    MERGE (p:Project {name: $project_name})
    MERGE (d:Decision {id: $decision_id})
    ON CREATE SET d.context = $decision_context,
                  d.created_at = $created_at,
                  d.confidence_score = $confidence_score,
                  d.governance_status = $governance_status
    ON MATCH SET  d.context = $decision_context,
                  d.confidence_score = $confidence_score,
                  d.governance_status = $governance_status
    MERGE (p)-[:REQUIRES_DECISION]->(d)

    // Outcome
    MERGE (rec:Recommendation {detail: $recommendation})
    MERGE (d)-[:RESULTS_IN]->(rec)
    """
    tx.run(query,
           project_name=data.project,
           decision_id=decision_id,
           decision_context=data.decision_context,
           recommendation=data.recommendation,
           created_at=datetime.now(timezone.utc).isoformat(),
           confidence_score=confidence_score,
           governance_status=governance_status)

    # 2. Evidence
    for ev in data.evidence:
        tx.run("""
        MATCH (d:Decision {id: $decision_id})
        MERGE (e:Evidence {detail: $detail})
        MERGE (d)-[:SUPPORTED_BY]->(e)
        """, decision_id=decision_id, detail=ev)

    # 3. Assumptions
    for assump in data.assumptions:
        tx.run("""
        MATCH (d:Decision {id: $decision_id})
        MERGE (a:Assumption {detail: $detail})
        MERGE (d)-[:DEPENDS_ON]->(a)
        """, decision_id=decision_id, detail=assump)

    # 4. Unknowns
    for unk in data.unknowns:
        tx.run("""
        MATCH (d:Decision {id: $decision_id})
        MERGE (u:Unknown {detail: $detail})
        MERGE (d)-[:LIMITED_BY]->(u)
        """, decision_id=decision_id, detail=unk)

    # 5. Risks
    for risk in data.risks:
        tx.run("""
        MATCH (d:Decision {id: $decision_id})
        MATCH (p:Project {name: $project_name})
        MERGE (r:Risk {detail: $detail})
        MERGE (d)-[:CARRIES_RISK]->(r)
        MERGE (r)-[:AFFECTS]->(p)
        """, decision_id=decision_id, project_name=data.project, detail=risk)

    # 6. Strategy — persist and link if provided
    if strategy:
        tx.run("""
        MATCH (d:Decision {id: $decision_id})
        MERGE (s:Strategy {decision_type: $decision_type})
        SET s.objective = $objective,
            s.risk_tolerance = $risk_tolerance,
            s.time_horizon = $time_horizon
        MERGE (d)-[:EVALUATED_UNDER]->(s)
        """,
        decision_id=decision_id,
        decision_type=strategy.decision_type,
        objective=strategy.objective,
        risk_tolerance=strategy.risk_tolerance,
        time_horizon=strategy.time_horizon)

    return decision_id


def insert_concept_lock(
    tx,
    decision_id: Optional[str],
    core_thesis: str,
    supporting_assumptions: list,
    risks: list,
    recommendations: list,
    open_unknowns: list,
    decision_conditions: list,
    required_validations: list,
    failure_triggers: list,
    monitoring_requirements: list,
    status: str,
):
    """Freezes a Council-approved pattern as a :ConceptLock node.

    Per the KORUM Concept Lock Workflow: the goal isn't to store the decision
    itself (that's the :Decision node) — it's to store the reasoning that
    produced an *approved* architecture, as a reusable institutional pattern.
    Linked back to its source Decision via LOCKED_AS when that decision is
    known (it may be None if Neo4j was offline at extraction time).

    Governance Conditions are kept as four distinct properties rather than
    one flattened list — decision_conditions, required_validations,
    failure_triggers, and monitoring_requirements answer different questions
    (approve / pre-execution gate / reversal trigger / ongoing Watchtower
    hook) and downstream consumers (Foundry Build, Watchtower) need to tell
    them apart. Neo4j properties can't hold nested maps, so each subfield is
    its own list property on the node; the API layer reassembles them into
    a nested "governance_conditions" object for clients.
    """
    lock_id = f"LOCK-{generate_id(core_thesis)}"

    query = """
    MERGE (lock:ConceptLock {id: $lock_id})
    ON CREATE SET lock.created_at = $created_at
    SET lock.core_thesis = $core_thesis,
        lock.status = $status,
        lock.supporting_assumptions = $supporting_assumptions,
        lock.risks = $risks,
        lock.recommendations = $recommendations,
        lock.open_unknowns = $open_unknowns,
        lock.decision_conditions = $decision_conditions,
        lock.required_validations = $required_validations,
        lock.failure_triggers = $failure_triggers,
        lock.monitoring_requirements = $monitoring_requirements,
        lock.locked_at = $locked_at
    """
    tx.run(query,
           lock_id=lock_id,
           created_at=datetime.now(timezone.utc).isoformat(),
           core_thesis=core_thesis,
           status=status,
           supporting_assumptions=supporting_assumptions,
           risks=risks,
           recommendations=recommendations,
           open_unknowns=open_unknowns,
           decision_conditions=decision_conditions,
           required_validations=required_validations,
           failure_triggers=failure_triggers,
           monitoring_requirements=monitoring_requirements,
           locked_at=datetime.now(timezone.utc).isoformat())

    if decision_id:
        tx.run("""
        MATCH (d:Decision {id: $decision_id})
        MATCH (lock:ConceptLock {id: $lock_id})
        MERGE (d)-[:LOCKED_AS]->(lock)
        """, decision_id=decision_id, lock_id=lock_id)

    return lock_id


def insert_blueprint_preview(tx, lock_id: str, blueprint):
    """Persist a test-harness Blueprint Preview linked to a Concept Lock."""
    blueprint_id = f"BPV-{generate_id(blueprint.product_brief)}"

    query = """
    MERGE (bp:BuildBlueprint {id: $blueprint_id})
    ON CREATE SET bp.created_at = $created_at
    SET bp.status = 'PREVIEW',
        bp.is_preview = true,
        bp.product_brief = $product_brief,
        bp.architecture_blueprint = $architecture_blueprint,
        bp.data_model = $data_model,
        bp.required_components = $required_components,
        bp.dependencies = $dependencies,
        bp.build_phases = $build_phases,
        bp.validation_gates = $validation_gates,
        bp.generated_at = $generated_at
    """
    tx.run(query,
           blueprint_id=blueprint_id,
           created_at=datetime.now(timezone.utc).isoformat(),
           product_brief=blueprint.product_brief,
           architecture_blueprint=blueprint.architecture_blueprint,
           data_model=blueprint.data_model,
           required_components=blueprint.required_components,
           dependencies=blueprint.dependencies,
           build_phases=blueprint.build_phases,
           validation_gates=blueprint.validation_gates,
           generated_at=datetime.now(timezone.utc).isoformat())

    tx.run("""
    MATCH (lock:ConceptLock {id: $lock_id})
    MATCH (bp:BuildBlueprint {id: $blueprint_id})
    MERGE (lock)-[:PREVIEWED_AS]->(bp)
    """, lock_id=lock_id, blueprint_id=blueprint_id)

    return blueprint_id
