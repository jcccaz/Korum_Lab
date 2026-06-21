# Spec: Replace templated escalation reasons with content-aware ones

Single-slice hand-off — **Codex builds this** (backend only, no frontend changes needed).

## Repo & file locations

Repo: `C:\Users\carlo\Projects\DecisionFormation` (NOT the `Foundry` repo)

Files you will edit, by absolute path:
- `C:\Users\carlo\Projects\DecisionFormation\korum_lab\extractor.py`
- `C:\Users\carlo\Projects\DecisionFormation\api.py`

New file you will create:
- `C:\Users\carlo\Projects\DecisionFormation\korum_lab\models\escalation.py`

## Problem

When a Strategy preset's required evidence isn't found in the extraction,
`api.py`'s `/api/extract` currently does this:

```python
missing = _check_required_evidence(evidence_list, strategy.required_evidence)
if missing:
    score -= 25
    for m in missing:
        governance_reason.append(f"Missing required evidence: {m}")
```

`m` comes straight from `STRATEGY_PRESETS[strategy].required_evidence` —
e.g. for "Strategic Planning" it's always exactly `"Market or competitive
analysis"` or `"Stakeholder or leadership input"`, verbatim, regardless of
what the decision is actually about. Every Strategic-Planning-tagged
decision that's missing that evidence gets the *identical* sentence. It
reads as templated because it is templated — it's a fixed string, not an
assessment of this decision.

Same root cause behind the `governance_status` label: when the resulting
score lands below 50, the status is hardcoded to `"CONTESTED BY RED TEAM"`
— even though no Red Team LLM call has run yet at this point in `/api/extract`
(Red Team Attack is a separate, later button). That label implies
adversarial review already happened; it hasn't.

## Fix

### 1. Escalation reasons — generate them from an LLM call, not a template

In `korum_lab/models/escalation.py`, add:

```python
from pydantic import BaseModel, Field
from typing import List

class EscalationAnalysis(BaseModel):
    reasons: List[str] = Field(
        description="One natural sentence per missing evidence type, explaining "
        "specifically why THIS decision needs that evidence — reference the "
        "decision's actual content (project, context, recommendation), not a "
        "generic restatement of the evidence category name."
    )
```

In `korum_lab/extractor.py`, add a new function (same `client.beta.chat.completions.parse`
pattern as `extract_structured_data` / `run_governor_resolution`):

```python
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
    missing (i.e. only on the escalation path), so this doesn't add cost to
    every extraction, only the ones that need a flagged gap explained.
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
```

(Import `EscalationAnalysis` from `korum_lab.models.escalation` at the top of `extractor.py`.)

### 2. Wire it into `api.py`, with a deterministic fallback

Replace the `if missing:` block in `/api/extract` with:

```python
if missing:
    score -= 25
    try:
        governance_reason.extend(
            generate_escalation_reasons(
                decision_context=data_dict["decision_context"],
                recommendation=data_dict["recommendation"],
                evidence=evidence_list,
                missing_evidence_types=missing,
                decision_type=strategy.decision_type,
            )
        )
    except Exception:
        # Never let an LLM hiccup block extraction — fall back to the old
        # templated phrasing rather than losing the escalation entirely.
        for m in missing:
            governance_reason.append(f"Missing required evidence: {m}")
```

### 3. Rename the misleading status label

Same function, a few lines down:

```python
if score >= 80:
    status = "NEURAL COUNCIL APPROVED"
    color = "success"
elif score >= 50:
    status = "HUMAN REVIEW REQUIRED"
    color = "warning"
else:
    status = "LOW CONFIDENCE — EVIDENCE GAP"   # was "CONTESTED BY RED TEAM"
    color = "danger"
```

This status is pre-Red-Team scoring math — keep the name honest about that
now that the reasons next to it are no longer obviously templated either.

## Acceptance test

1. Run the same ANCHOR-INDEX scenario from today's manual test (Strategic Planning,
   missing "Market or competitive analysis" and "Stakeholder or leadership input").
2. Escalation Triggers panel shows two sentences that reference "ANCHOR-INDEX" /
   "foundry_builds" / the actual recommendation — not the literal phrases
   "Market or competitive analysis" or "Stakeholder or leadership input" verbatim.
3. Run it twice with the *same* input — the two sentences may vary in wording
   (it's an LLM call) but should always name the same two missing categories.
4. Temporarily break `OPENAI_API_KEY` (or simulate a failure) and confirm the
   fallback produces the old templated strings instead of crashing the request.
5. Status badge for a sub-50 score now reads "LOW CONFIDENCE — EVIDENCE GAP",
   not "CONTESTED BY RED TEAM", anywhere in the response and in `KorumDashboard.tsx`'s
   rendering of `governance_status` (no frontend code change needed — it just
   displays whatever string `api.py` sends).
