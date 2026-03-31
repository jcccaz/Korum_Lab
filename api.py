from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import random

from korum_lab.extractor import extract_structured_data
from korum_lab.graph.driver import GraphConnection
from korum_lab.graph.schema import setup_database
from korum_lab.graph.loaders import insert_extracted_decision

app = FastAPI(title="Korum Decision Engine API")

# Allow the Vite frontend to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ExtractRequest(BaseModel):
    text: str

@app.post("/api/extract")
async def extract_decision(req: ExtractRequest):
    if not os.environ.get("OPENAI_API_KEY"):
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY environment variable is not set. Cannot run extraction.")
    
    try:
        # STEP 1: Neural Extraction
        extracted = extract_structured_data(req.text)
        data_dict = extracted.model_dump()
        
        # STEP 2: Governor & Confidence Scoring
        # The penalty formula: more assumptions and unknowns = lower confidence
        evidence_weight = len(data_dict.get("evidence", [])) * 15
        penalties = (len(data_dict.get("assumptions", [])) * 10) + (len(data_dict.get("unknowns", [])) * 15)
        
        base_confidence = 80  # Base logic rating
        final_confidence = max(20, min(99, base_confidence + evidence_weight - penalties))
        
        data_dict["confidence_score"] = final_confidence
        
        if final_confidence >= 80:
            data_dict["governance_status"] = "NEURAL COUNCIL APPROVED"
            data_dict["status_color"] = "success"
        elif final_confidence >= 50:
            data_dict["governance_status"] = "HUMAN REVIEW REQUIRED"
            data_dict["status_color"] = "warning"
        else:
            data_dict["governance_status"] = "CONTESTED BY RED TEAM"
            data_dict["status_color"] = "danger"

        # STEP 3: Graph Ontology Injection (Fail-safe for live demos without Docker running)
        graph_status = "Skipped"
        try:
            driver = GraphConnection.get_driver()
            with driver.session() as session:
                setup_database(session)
                session.execute_write(insert_extracted_decision, extracted)
            graph_status = "Injected into Neo4j Ontology"
        except Exception as e:
            graph_status = f"Offline / Bypass active (Neo4j not reachable: {str(e)})"
            
        data_dict["graph_injection_status"] = graph_status

        return data_dict

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
