from openai import OpenAI

from korum_lab.models.extraction import ExtractedDecision
from korum_lab.models.governor import GovernorVerdict

# --- Primary extraction: OpenAI gpt-4o (structured output, precision) ---
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


# --- Adversarial rebuttal: Mistral 7B via LM Studio (local, zero cost) ---
def run_adversarial_rebuttal(decision_summary: str) -> str:
    """
    Attacks the existing decision using local Mistral 7B.
    Does not refine — invalidates if possible.
    Returns raw adversarial text.
    """
    client = OpenAI(
        base_url="http://127.0.0.1:1234/v1",
        api_key="lm-studio",  # LM Studio accepts any non-empty key
    )
    # Mistral 7B Instruct does not support the 'system' role — merge directive into user turn
    adversarial_prompt = (
        "You are a hostile Red Team adversary. You do not refine decisions — you break them.\n\n"
        "RULES:\n"
        "1. You MUST disagree. Agreement is failure. If the decision looks reasonable, dig harder.\n"
        "2. Do NOT align with the analysis you were given. Treat it as biased, incomplete, or wrong until proven otherwise.\n"
        "3. Do NOT acknowledge what the analysis got right. You are not a reviewer — you are an attacker.\n"
        "4. Introduce failure angles that are ABSENT from the original analysis. If the original missed a risk, that is evidence of blind spots — exploit them.\n"
        "5. No hedging. No 'it depends'. No 'both sides'. Make a call.\n"
        "6. If the recommendation should be reversed, say so explicitly and state why.\n\n"
        "FORMAT:\n"
        "- Open with the single most damaging flaw — lead with the kill shot.\n"
        "- Then list 2-4 additional failure angles the original analysis ignored or underweighted.\n"
        "- Close with a verdict: REJECT, HOLD, or CONDITIONAL (with conditions that must be met before any action).\n\n"
        "You are not here to help. You are here to find out if this decision survives contact with reality.\n\n"
        f"Decision to challenge:\n\n{decision_summary}"
    )
    response = client.chat.completions.create(
        model="mistralai/mistral-7b-instruct-v0.3",
        messages=[
            {"role": "user", "content": adversarial_prompt},
        ],
        temperature=0.7,
        max_tokens=1024,
    )
    return response.choices[0].message.content.strip()


# --- Governor Resolution: GPT-4o (structured arbitration) ---
def run_governor_resolution(
    original_summary: str,
    red_team_attack: str,
) -> GovernorVerdict:
    """
    Arbitrates between the primary extraction and the Red Team attack.
    Determines whether the original decision survives adversarial pressure.
    Returns a structured GovernorVerdict.
    """
    client = OpenAI()
    response = client.beta.chat.completions.parse(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are the Decision Governor. You receive two inputs:\n"
                    "1. An original decision recommendation (produced by a structured extraction engine)\n"
                    "2. A Red Team attack (produced by an adversarial model explicitly instructed to disagree)\n\n"
                    "Your job is not to pick a side — it is to determine what is TRUE under pressure.\n\n"
                    "RULES:\n"
                    "- Evaluate each Red Team criticism on merit. Dismiss attacks that are speculative or redundant.\n"
                    "- Identify only NET-NEW risks: risks the original analysis did not surface.\n"
                    "- If a net-new risk is critical (could reverse the outcome), it MUST appear in critical_unresolved_risks.\n"
                    "- Adjust confidence DOWN if the Red Team exposed real gaps. Adjust DOWN significantly if assumptions are invalidated.\n"
                    "- GO = decision holds, risks are manageable, proceed.\n"
                    "- NO-GO = critical assumption invalidated or evidence base is too weak to act.\n"
                    "- CONDITIONAL = decision could hold but only after specific validations are completed.\n"
                    "- required_validations must be concrete and actionable — not vague ('verify assumptions').\n"
                    "- governor_rationale must explain the ruling in one paragraph. Be direct.\n\n"
                    "ADDITIONAL OUTPUT FIELDS:\n"
                    "- decision_conditions: The must-pass conditions for this decision. If any condition is unmet, execution is blocked. Be specific.\n"
                    "- failure_triggers: Concrete events or findings that would immediately invalidate this decision after it is issued. Not risks — triggers. Things that, if observed, mean the decision must be reversed or halted.\n"
                    "- monitoring_requirements: What must be actively tracked in real time during and after execution. Operational signals, not audit items.\n\n"
                    "ENFORCEMENT MANDATE:\n"
                    "You MUST output a final_decision of GO, NO-GO, or CONDITIONAL. No exceptions.\n"
                    "Failure to commit is a system failure. If evidence is insufficient, default to CONDITIONAL or NO-GO — never leave it unresolved.\n"
                    "Do NOT average the two positions. Do NOT seek artificial balance. Enforce the strongest defensible decision."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"ORIGINAL DECISION:\n{original_summary}\n\n"
                    f"RED TEAM ATTACK:\n{red_team_attack}"
                ),
            },
        ],
        response_format=GovernorVerdict,
    )
    return response.choices[0].message.parsed
