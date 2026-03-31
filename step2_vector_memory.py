import os
import json
import chromadb
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction

# Import our exact extraction logic from Step 1
from step1_extraction import extract_structured_data

# =====================================================================
# STEP 2: VECTOR DB (The Memory Layer)
# This is "semantic memory". We store unstructured text.
# We also attach the structured metadata from Step 1 so we have both:
#   1. Semantic Search (find by meaning)
#   2. Structured Filters (filter by exact risk/confidence)
# =====================================================================

def get_chroma_collection():
    # We use a PersistentClient so data survives between runs!
    # It stores the DB in a local folder called "chroma_db"
    db_path = os.path.join(os.path.dirname(__file__), "chroma_db")
    client = chromadb.PersistentClient(path=db_path)
    
    # We use OpenAI embeddings (requires OPENAI_API_KEY)
    # This automatically converts our text into mathematical vectors
    embedding_fn = OpenAIEmbeddingFunction(
        api_key=os.environ.get("OPENAI_API_KEY"),
        model_name="text-embedding-3-small"
    )
    
    # Get or create the collection
    collection = client.get_or_create_collection(
        name="decision_memory",
        embedding_function=embedding_fn
    )
    
    return collection

def ingest_to_memory(doc_id: str, text: str):
    print(f"\n[Ingesting] {doc_id}...")
    
    # 1. Run our Graph-defined Extractor (Step 1)
    print("  -> Parsing unstructured text into Master Schema...")
    structured_data = extract_structured_data(text)
    
    # 2. Get the DB collection
    collection = get_chroma_collection()
    
    # 3. Store the text AND the exact metadata in Chroma
    # We must convert the 'facts' list to a string because Chroma metadata only accepts str/int/float/bool
    metadata = {
        "risk": structured_data.risk,
        "confidence": structured_data.confidence,
        "facts": json.dumps(structured_data.facts)
    }
    
    # We use upsert so it updates if the ID already exists
    collection.upsert(
        documents=[text],
        metadatas=[metadata],
        ids=[doc_id]
    )
    print(f"  -> Added to Vector DB with metadata: {metadata}")

def search_memory(query: str):
    print(f"\n[Searching] Query: '{query}'")
    collection = get_chroma_collection()
    
    # Retrieve the top 2 most semantically similar chunks
    results = collection.query(
        query_texts=[query],
        n_results=2
    )
    
    # Print out what we found
    if not results["ids"][0]:
        print("  No results found.")
        return

    for i in range(len(results["ids"][0])):
        doc_id = results["ids"][0][i]
        text = results["documents"][0][i]
        meta = results["metadatas"][0][i]
        distance = results["distances"][0][i]
        
        # In Chroma, a lower distance means it is mathematically closer (more similar)
        print(f"\n--- Result {i+1} (Distance: {distance:.4f}) ---")
        print(f"ID: {doc_id}")
        print(f"Text: {text}")
        print(f"Extracted Risk: {meta['risk']}")
        print(f"Extracted Confidence: {meta['confidence']}")
        print(f"Extracted Facts: {meta['facts']}")


if __name__ == "__main__":
    import sys
    
    if "OPENAI_API_KEY" not in os.environ:
        print("[!] ERROR: Please set OPENAI_API_KEY as an environment variable first.")
        sys.exit(1)
        
    print("===== KORUM PROTO: STEP 2 (VECTOR MEMORY) =====")
    
    # Pretend these are 3 distinct unstructured reports crossing the Korum desk
    doc1 = "Revenue increased 15% but costs rose 22% due to supply issues in the APAC region. Expected margin compression."
    doc2 = "The new CRM deployment is delayed by 3 weeks. Leadership is frustrated, but the technical team needs more time for security reviews."
    doc3 = "Sales in Europe exceeded expectations by 5%. The marketing campaign in Germany was highly effective."
    
    print("\n>>> INGESTING UNSTRUCTURED DATA TO MEMORY")
    ingest_to_memory("report_q3_apac", doc1)
    ingest_to_memory("crm_update_01", doc2)
    ingest_to_memory("europe_sales_01", doc3)
    
    print("\n>>> TESTING SEMANTIC SEARCH")
    # Searching for meaning, not exact keywords! Notice how these questions don't contain exact words from the docs.
    search_memory("Are we facing any financial problems or margin reduction in Asia?")
    search_memory("How are our IT and software deployments going?")

    print("\n[✔] Step 2 Complete.")
