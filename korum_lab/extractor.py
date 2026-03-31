import json
from openai import OpenAI

from korum_lab.models.extraction import ExtractedDecision

def extract_structured_data(text: str) -> ExtractedDecision:
    """Takes unstructured text and forces it into the Korum Graph Ontology."""
    client = OpenAI()
    response = client.beta.chat.completions.parse(
        model="gpt-4o",
        messages=[
            {
                "role": "system", 
                "content": "You are Korum Lab's intelligence extraction engine. Extract the decision context, hard evidence, assumptions, risks, unknowns, and the final recommendation."
            },
            {"role": "user", "content": f"Text:\n\n{text}"}
        ],
        response_format=ExtractedDecision,
    )
    return response.choices[0].message.parsed
