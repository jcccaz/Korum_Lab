import os

# --- Neo4j Graph Connection ---
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "korumlab123")
NEO4J_AUTH = (NEO4J_USER, NEO4J_PASSWORD)

# --- Vector DB / Memory Connection ---
CHROMA_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "chroma_db")
