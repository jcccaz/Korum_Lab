def query_project_risks(tx, project_name):
    """Finds all risks that currently affect a specific project by traversing the graph."""
    query = """
    MATCH (p:Project {name: $project_name})<-[:AFFECTS]-(r:Risk)
    RETURN p.name AS project, r.detail AS risk
    """
    result = tx.run(query, project_name=project_name)
    return [{"project": record["project"], "risk": record["risk"]} for record in result]

def query_list_decisions(tx, limit=50):
    """Lists past decisions (most recent first) for the Korum Lab history panel.

    Older decisions written before created_at existed fall back to last in
    the result set via coalesce(), rather than being hidden or erroring out.
    """
    query = """
    MATCH (d:Decision)
    OPTIONAL MATCH (p:Project)-[:REQUIRES_DECISION]->(d)
    RETURN d.id AS id,
           d.context AS decision_context,
           p.name AS project,
           d.confidence_score AS confidence_score,
           d.governance_status AS governance_status,
           coalesce(d.created_at, '') AS created_at
    ORDER BY created_at DESC
    LIMIT $limit
    """
    result = tx.run(query, limit=limit)
    return [dict(record) for record in result]


def query_decision_by_id(tx, decision_id):
    """Reconstructs a single past decision (by graph id) for reloading into the lab UI."""
    query = """
    MATCH (d:Decision {id: $decision_id})
    OPTIONAL MATCH (p:Project)-[:REQUIRES_DECISION]->(d)
    OPTIONAL MATCH (d)-[:SUPPORTED_BY]->(e:Evidence)
    OPTIONAL MATCH (d)-[:DEPENDS_ON]->(a:Assumption)
    OPTIONAL MATCH (d)-[:LIMITED_BY]->(u:Unknown)
    OPTIONAL MATCH (d)-[:CARRIES_RISK]->(r:Risk)
    OPTIONAL MATCH (d)-[:RESULTS_IN]->(rec:Recommendation)
    OPTIONAL MATCH (d)-[:EVALUATED_UNDER]->(s:Strategy)
    RETURN d.id AS id,
           d.context AS decision_context,
           p.name AS project,
           d.confidence_score AS confidence_score,
           d.governance_status AS governance_status,
           d.created_at AS created_at,
           collect(DISTINCT e.detail) AS evidence,
           collect(DISTINCT a.detail) AS assumptions,
           collect(DISTINCT u.detail) AS unknowns,
           collect(DISTINCT r.detail) AS risks,
           collect(DISTINCT rec.detail)[0] AS recommendation,
           s.decision_type AS strategy_decision_type,
           s.objective AS strategy_objective
    """
    result = tx.run(query, decision_id=decision_id)
    record = result.single()
    return dict(record) if record else None


def query_concept_lock(tx, lock_id):
    """Fetches a single Concept Lock by id, with the Decision it was frozen from (if known).

    Governance Conditions come back as four flat properties (Neo4j has no
    nested-map property type) — the caller (api.py) reassembles them into a
    nested governance_conditions object before returning to clients.
    """
    query = """
    MATCH (lock:ConceptLock {id: $lock_id})
    OPTIONAL MATCH (d:Decision)-[:LOCKED_AS]->(lock)
    RETURN lock.id AS id,
           lock.core_thesis AS core_thesis,
           lock.status AS status,
           lock.supporting_assumptions AS supporting_assumptions,
           lock.risks AS risks,
           lock.recommendations AS recommendations,
           lock.open_unknowns AS open_unknowns,
           lock.decision_conditions AS decision_conditions,
           lock.required_validations AS required_validations,
           lock.failure_triggers AS failure_triggers,
           lock.monitoring_requirements AS monitoring_requirements,
           lock.locked_at AS locked_at,
           d.id AS decision_id
    """
    result = tx.run(query, lock_id=lock_id)
    record = result.single()
    return dict(record) if record else None


def query_preview_for_lock(tx, lock_id):
    """Fetches the latest Blueprint Preview for a Concept Lock."""
    query = """
    MATCH (lock:ConceptLock {id: $lock_id})-[:PREVIEWED_AS]->(bp:BuildBlueprint)
    RETURN bp.id AS id,
           bp.product_brief AS product_brief,
           bp.architecture_blueprint AS architecture_blueprint,
           bp.data_model AS data_model,
           bp.required_components AS required_components,
           bp.dependencies AS dependencies,
           bp.build_phases AS build_phases,
           bp.validation_gates AS validation_gates,
           bp.generated_at AS generated_at
    ORDER BY bp.generated_at DESC LIMIT 1
    """
    result = tx.run(query, lock_id=lock_id)
    record = result.single()
    return dict(record) if record else None


def query_decision_foundation(tx, project_name):
    """Reconstructs the 'Why' of a decision by mapping its foundation (evidence vs assumptions)."""
    query = """
    MATCH (p:Project {name: $project_name})-[:REQUIRES_DECISION]->(d:Decision)
    OPTIONAL MATCH (d)-[:SUPPORTED_BY]->(e:Evidence)
    OPTIONAL MATCH (d)-[:DEPENDS_ON]->(a:Assumption)
    OPTIONAL MATCH (d)-[:LIMITED_BY]->(u:Unknown)
    RETURN d.context AS decision, 
           collect(DISTINCT e.detail) AS evidence, 
           collect(DISTINCT a.detail) AS assumptions,
           collect(DISTINCT u.detail) AS unknowns
    """
    result = tx.run(query, project_name=project_name)
    return [{
        "decision": record["decision"],
        "evidence": record["evidence"],
        "assumptions": record["assumptions"],
        "unknowns": record["unknowns"]
    } for record in result]
