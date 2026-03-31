def query_project_risks(tx, project_name):
    """Finds all risks that currently affect a specific project by traversing the graph."""
    query = """
    MATCH (p:Project {name: $project_name})<-[:AFFECTS]-(r:Risk)
    RETURN p.name AS project, r.detail AS risk
    """
    result = tx.run(query, project_name=project_name)
    return [{"project": record["project"], "risk": record["risk"]} for record in result]

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
