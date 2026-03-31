import sys
import os
from pathlib import Path

# Import components from our modular architecture
from korum_lab.extractor import extract_structured_data
from korum_lab.graph.driver import GraphConnection
from korum_lab.graph.schema import setup_database
from korum_lab.graph.loaders import insert_extracted_decision
from korum_lab.graph.queries import query_project_risks, query_decision_foundation

INPUT_PATH = Path(__file__).resolve().parent / "inputs" / "scenario.txt"


def get_input_text() -> str:
    if len(sys.argv) > 1:
        input_path = Path(sys.argv[1]).expanduser()
    else:
        input_path = INPUT_PATH

    try:
        return input_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        print(f"[!] ERROR: Input file not found: {input_path}")
        sys.exit(1)
    except Exception as exc:
        print(f"[!] ERROR reading input file {input_path}: {exc}")
        sys.exit(1)


def run_lab():
    if "OPENAI_API_KEY" not in os.environ:
        print("[!] ERROR: Set OPENAI_API_KEY environment variable first.")
        sys.exit(1)

    print("===== KORUM LAB: FULL ORCHESTRATION COMPLETED =====")
    
    # 1. Messy Input Data
    sample_text = get_input_text()
    
    # [STEP 1] Extraction
    print("\n[Stage 1] Extracting Unstructured Intelligence...")
    structured_data = extract_structured_data(sample_text)
    print(f" -> Found Project: {structured_data.project}")
    print(f" -> Found Decision: {structured_data.decision_context}")
    
    try:
        # Get singleton connection
        driver = GraphConnection.get_driver()
        with driver.session() as session:
            # [STEP 2] Graph Constraints
            print("\n[Stage 2] Enforcing Database Constraints (Primary Keys)...")
            setup_database(session)
            
            # [STEP 4] Orchestration: Pydantic -> Cypher Injection
            print("\n[Stage 3] Loading Extracted Decision into the Graph Ontology...")
            session.execute_write(insert_extracted_decision, structured_data)
            print(" -> Nodes and relationship edges created based on Korum rules.")
            
            # The Payoff!
            print("\n[Stage 4] Interrogating the Decision Graph...")
            
            print("\n-- Query 1: What are all the risks affecting Project Apollo?")
            risks = session.execute_read(query_project_risks, structured_data.project)
            if not risks:
                print("   (No risks found)")
            for r in risks:
                print(f"   ► Risk to {r['project']}: {r['risk']}")
                
            print("\n-- Query 2: What is the exact foundation driving the Apollo decision?")
            foundation = session.execute_read(query_decision_foundation, structured_data.project)
            for f in foundation:
                print(f"   ► Context: {f['decision']}")
                print(f"       ✅ Evidence:    {'; '.join(f['evidence']) if f['evidence'] else '(none)'}")
                print(f"       ⚠️ Assumptions: {'; '.join(f['assumptions']) if f['assumptions'] else '(none)'}")
                print(f"       ❓ Unknowns:    {'; '.join(f['unknowns']) if f['unknowns'] else '(none)'}")
                
        GraphConnection.close()
        print("\n[✔] Orchestration Complete. We just turned a messy email into an auditable intelligence graph.")
    except Exception as e:
        print(f"\n[!] Error connecting to Graph DB. Is Docker running? (Error: {e})")

if __name__ == "__main__":
    run_lab()
