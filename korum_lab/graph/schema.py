def setup_database(session):
    """
    Like primary keys for reality.
    Neo4j will error out if you try to make two nodes with the same 'unique' ID instead of duplicating them.
    NOTE: CREATE CONSTRAINT is a schema (DDL) operation — it cannot run inside a write transaction.
    It must be run directly on the session.
    """
    queries = [
        "CREATE CONSTRAINT project_name IF NOT EXISTS FOR (n:Project) REQUIRE n.name IS UNIQUE",
        "CREATE CONSTRAINT decision_id IF NOT EXISTS FOR (n:Decision) REQUIRE n.id IS UNIQUE",
        "CREATE CONSTRAINT evidence_item IF NOT EXISTS FOR (n:Evidence) REQUIRE n.detail IS UNIQUE",
        "CREATE CONSTRAINT assumption_item IF NOT EXISTS FOR (n:Assumption) REQUIRE n.detail IS UNIQUE",
        "CREATE CONSTRAINT unknown_item IF NOT EXISTS FOR (n:Unknown) REQUIRE n.detail IS UNIQUE",
        "CREATE CONSTRAINT risk_item IF NOT EXISTS FOR (n:Risk) REQUIRE n.detail IS UNIQUE",
        "CREATE CONSTRAINT recommendation_item IF NOT EXISTS FOR (n:Recommendation) REQUIRE n.detail IS UNIQUE",
    ]
    for q in queries:
        session.run(q)
