import hashlib

def generate_id(text: str) -> str:
    """Generates a reliable hash ID based on the decision context text."""
    return hashlib.md5(text.encode('utf-8')).hexdigest()[:8]

def insert_extracted_decision(tx, data):
    """Inserts a Pydantic 'ExtractedDecision' straight into the Neo4j graph using the Korum Ontology."""
    
    # Generate unique ID for the central decision node
    decision_id = f"DEC-{generate_id(data.decision_context)}"
    
    # 1. Base nodes: Project & Decision
    query = """
    MERGE (p:Project {name: $project_name})
    MERGE (d:Decision {id: $decision_id}) 
    SET d.context = $decision_context
    MERGE (p)-[:REQUIRES_DECISION]->(d)
    
    // Outcome
    MERGE (rec:Recommendation {detail: $recommendation})
    MERGE (d)-[:RESULTS_IN]->(rec)
    """
    tx.run(query, 
           project_name=data.project, 
           decision_id=decision_id, 
           decision_context=data.decision_context,
           recommendation=data.recommendation)
           
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
        # A risk carries from the decision and immediately affects the project
        tx.run("""
        MATCH (d:Decision {id: $decision_id})
        MATCH (p:Project {name: $project_name})
        MERGE (r:Risk {detail: $detail})
        MERGE (d)-[:CARRIES_RISK]->(r)
        MERGE (r)-[:AFFECTS]->(p)
        """, decision_id=decision_id, project_name=data.project, detail=risk)
