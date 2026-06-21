from openai import OpenAI
from typing import List

from korum_lab.models.extraction import ExtractedDecision
from korum_lab.models.governor import GovernorVerdict
from korum_lab.models.blueprint import BuildBlueprint
from korum_lab.models.escalation import EscalationAnalysis

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


def generate_escalation_reasons(
    decision_context: str,
    recommendation: str,
    evidence: List[str],
    missing_evidence_types: List[str],
    decision_type: str,
) -> List[str]:
    """
    Replaces the old templated 'Missing required evidence: X' strings with
    reasoning grounded in the actual decision — not a copy of the Strategy
    preset's required_evidence phrase. Called only when required evidence is
    missing, so this adds cost only to requests that need an escalation gap
    explained.
    """
    client = OpenAI()
    response = client.beta.chat.completions.parse(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": (
                    "You explain evidence gaps for a governed decision pipeline. "
                    "You are given a decision, its current evidence and recommendation, "
                    "and a list of evidence categories that are missing per the "
                    f"'{decision_type}' strategy. Write ONE sentence per missing "
                    "category, specific to THIS decision — name the actual project/"
                    "recommendation, don't just restate the category name. Do not "
                    "soften or hedge; these are escalation flags, not suggestions."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"DECISION: {decision_context}\n"
                    f"RECOMMENDATION: {recommendation}\n"
                    f"EXISTING EVIDENCE: {'; '.join(evidence) or 'None'}\n"
                    f"MISSING EVIDENCE CATEGORIES: {', '.join(missing_evidence_types)}"
                ),
            },
        ],
        response_format=EscalationAnalysis,
    )
    return response.choices[0].message.parsed.reasons


# --- Foundry Workshop Build: GPT-4o (structured planning, NOT code generation) ---
def run_blueprint_generation(concept_lock_summary: str) -> BuildBlueprint:
    """
    Forge MVP — Build Blueprint Generator.

    Takes a locked Concept Lock (an approved, governed decision) and answers
    "How would we build this?" — NOT "generate the application." This is
    intentionally scoped down from the full Forge vision: no code synthesis,
    no repo generation, no deployment plan. Just the planning artifacts a
    human (or a future, fuller Forge) would need before writing a line of
    code: a product brief, an architecture narrative, a conceptual data
    model, required components, dependencies, ordered build phases, and the
    validation gates between them.

    This exists to test one specific handoff — can an approved Concept Lock
    reliably become an actionable implementation blueprint? — before
    building anything bigger.
    """
    client = OpenAI()
    response = client.beta.chat.completions.parse(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are Forge's Build Blueprint Generator — the first stage of Foundry "
                    "Workshop Build. You receive an approved, governed Concept Lock (a frozen "
                    "institutional decision pattern, already through Council and Governor "
                    "review) and must answer ONE question: How would we build this?\n\n"
                    "HARD BOUNDARIES — violating any of these is a failure:\n"
                    "- Do NOT write code. No snippets, no pseudocode, no file contents.\n"
                    "- Do NOT generate a repository structure, file tree, or scaffold.\n"
                    "- Do NOT produce a deployment plan or CI/CD steps.\n"
                    "- Do NOT answer 'generate the application' — you are answering 'how would "
                    "we build this', which is a planning question, not a construction one.\n\n"
                    "WHAT TO DO INSTEAD:\n"
                    "- product_brief: ground this in the Concept Lock's actual Core Thesis and "
                    "Recommendations — not a generic pitch.\n"
                    "- architecture_blueprint: describe the major pieces and how they relate, "
                    "in prose. A reader should understand the shape of the system, not its code.\n"
                    "- data_model: name the key entities/structures conceptually — not SQL/Cypher.\n"
                    "- required_components: name services/modules/pieces that must exist.\n"
                    "- dependencies: external libraries, APIs, infrastructure, other KORUM "
                    "systems (e.g. ANCHOR, Watchtower) this would need to integrate with.\n"
                    "- build_phases: an ORDERED sequence — sequence matters, don't just list "
                    "everything as parallel work.\n"
                    "- validation_gates: what must pass before moving to the next phase. Pull "
                    "from the Concept Lock's Governance Conditions where relevant, but make "
                    "these specific to the build itself, not just a restatement of them.\n\n"
                    "If the Concept Lock doesn't give you enough to answer a field with "
                    "confidence, say so explicitly in that field rather than inventing detail."
                ),
            },
            {
                "role": "user",
                "content": f"CONCEPT LOCK:\n\n{concept_lock_summary}",
            },
        ],
        response_format=BuildBlueprint,
    )
    return response.choices[0].message.parsed
