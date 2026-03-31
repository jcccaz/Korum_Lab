import json
import os
from openai import OpenAI
from pydantic import BaseModel
from typing import List

# =====================================================================
# STEP 1: STRUCTURED EXTRACTION (The Foundation)
# This is the "Graph defines what can exist" phase — creating an exact shape.
# We use Pydantic to strictly define the schema we want back from the LLM.
# =====================================================================

class ExtractionResult(BaseModel):
    facts: List[str]
    risk: str
    confidence: str

def extract_structured_data(text: str) -> ExtractionResult:
    """Takes unstructured text and strictly forces it into a JSON schema."""
    
    # Initialize the OpenAI client (Assumes OPENAI_API_KEY is in environment)
    client = OpenAI()
    
    # We use the beta .parse() method which guarantees strict adherence 
    # to the Pydantic schema using Structured Outputs.
    response = client.beta.chat.completions.parse(
        model="gpt-4o", # You can swap this for whatever model you prefer
        messages=[
            {"role": "system", "content": "You are a master of structured data extraction. Extract the facts, a primary risk, and an overall confidence level (low, medium, high)."},
            {"role": "user", "content": f"Text:\n\n{text}"}
        ],
        response_format=ExtractionResult,
    )
    
    return response.choices[0].message.parsed

if __name__ == "__main__":
    # The messy, unstructured reality
    sample_input = "Revenue increased 15% but costs rose 22% due to supply issues in the APAC region. We expect a margin compression of 3% next quarter."
    
    print("--- RAW INPUT (Unstructured) ---")
    print(sample_input)
    print("\n--- STRUCTURED OUTPUT (The Master Schema) ---")
    
    try:
        # Note: Ensure you have your OPENAI_API_KEY set in your terminal:
        # $env:OPENAI_API_KEY="sk-..." 
        result = extract_structured_data(sample_input)
        
        # Print out the structured Pydantic object as clean JSON
        print(result.model_dump_json(indent=2))
        
    except Exception as e:
        print(f"\n[!] Error during extraction (Did you set OPENAI_API_KEY?): {e}")
