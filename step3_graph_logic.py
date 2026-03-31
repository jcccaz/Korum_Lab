from neo4j import GraphDatabase
from korum_lab.config import NEO4J_URI, NEO4J_AUTH

# =====================================================================
# STEP 3: GRAPH DB (The Leap)
# This is where we stop thinking in tables/documents and start thinking
# in relationships.
# "Graph defines what can exist."
# =====================================================================

def init_driver():
    return GraphDatabase.driver(NEO4J_URI, auth=NEO4J_AUTH)

def create_ontology(tx):
    # This creates the exact ontology Stephan was talking about.
    # We define nodes (Carlos, Korum, Decision) and how they relate.
    query = """
    // 1. Define the entities
    MERGE (c:Person {name: 'Carlos'})
    MERGE (k:System {name: 'Korum Lab'})
    MERGE (d:Concept {name: 'Defensible Decisions'})
    MERGE (e:Concept {name: 'Evidence'})
    
    // 2. Define the exact relationships
    MERGE (c)-[:BUILDS]->(k)
    MERGE (k)-[:ENABLES]->(d)
    MERGE (d)-[:REQUIRES]->(e)
    """
    tx.run(query)

def create_practical_risk_graph(tx, project_name, risk_level, delay_reason):
     # A more practical example based on our Step 1/2 Extractor
     query = """
     MERGE (p:Project {name: $project_name})
     MERGE (r:Risk {level: $risk_level})
     MERGE (d:Delay {reason: $delay_reason})
     
     MERGE (p)-[:FACES_RISK]->(r)
     MERGE (p)-[:DELAYED_BY]->(d)
     """
     tx.run(query, project_name=project_name, risk_level=risk_level, delay_reason=delay_reason)

def query_ontology(tx):
    # "What requires Evidence?"
    query = """
    MATCH (n)-[:REQUIRES]->(e:Concept {name: 'Evidence'})
    RETURN n.name AS concept
    """
    result = tx.run(query)
    return [record["concept"] for record in result]

if __name__ == "__main__":
    print("===== KORUM LAB: STEP 3 (GRAPH ONTOLOGY) =====")
    
    try:
        driver = init_driver()
        with driver.session() as session:
            print("1. Injecting Ontology (The rules of reality) into Graph...")
            session.execute_write(create_ontology)
            
            print("2. Mapping a concrete business risk to the Graph...")
            # Imagine we extracted these fields via LLM in Step 1
            session.execute_write(create_practical_risk_graph, "CRM Deployment", "High", "Security Reviews")
            
            print("3. Querying Graph Relationships (What needs evidence?)....")
            concepts = session.execute_read(query_ontology)
            print(f"   -> Result: {concepts}")
            
        print("\n[✔] Step 3 Complete. The Graph now holds the rules.")
        driver.close()
    except Exception as e:
        print(f"\n[!] Error: Could not connect to Neo4j. Is the Docker container running? (Error: {e})")
