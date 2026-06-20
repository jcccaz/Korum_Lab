# Korum–Neo4j Segmentation Plan: Retrieval, Adjudication, and Write-Back Loop

> **The architectural sentence:**
> Neo4j is the memory and comparison layer. Korum is the adjudication and governance layer.
> The write-back loop turns each decision into reusable future intelligence.
>
> **The central rule:**
> The graph must grow in quality, not volume.

---

## Segment 1 — Retrieval

**Purpose:**
Before Korum touches the current scenario, Neo4j is queried for high-signal memory.
The goal is to surface what is already known — not to rediscover it during adjudication.

**What gets pulled:**
- Similar prior scenarios (matched by decision type, domain, project pattern)
- Prior Red Team attack themes against similar decisions
- Rebuttal patterns that succeeded in reducing adversarial pressure
- Governor outcome history (what GOT downgraded, what held as GO, what was CONDITIONAL)
- Confidence warning patterns (decisions that started high and were downgraded)

**Rules:**
- No raw graph dump
- No noisy node soup
- Only decision-relevant signals
- Return structured, compact packets — not raw Cypher output

**Output — Neo4j → Korum Handoff Packet:**
```
{
  "current_scenario_context": "...",
  "matched_prior_scenarios": [...],
  "repeated_attack_themes": [...],
  "successful_rebuttal_patterns": [...],
  "prior_governor_downgrades": [...],
  "confidence_warnings": [...]
}
```

---

## Segment 2 — Adjudication

**Purpose:**
Korum evaluates the current scenario using the full council pipeline:
Extract → Red Team Challenge → Governor Resolution.

It uses the retrieval packet as context — not as a crutch.
Korum judges. It does not scavenge history.

**What Korum does:**
- Runs the current scenario through structured extraction (GPT-4o)
- Attacks the decision with Red Team (Mistral 7B local)
- Compares current attack themes against retrieved prior attack patterns
- Runs Governor arbitration (3-step: rule checks → LLM → hard enforcement)
- Produces final score, status, rationale, and delta vs prior similar decisions

**Rules:**
- Korum does not waste cycles rediscovering what Neo4j already knows
- Retrieval context informs — it does not override
- Governor verdict is always freshly computed — never inherited from graph

---

## Segment 3 — Write-Back

**Purpose:**
After adjudication, persist only what matters.
Update the living graph with the final outcome.
Capture what changed confidence, score, or status.

**Rules:**
- Quality over volume
- No transcript dumping
- No conversational filler
- No duplicate claims
- No low-signal side chatter
- No temporary reasoning fragments
- No raw transcript blobs
- Only durable knowledge objects and state changes

**Output — Korum → Neo4j Write-Back Packet:**
```
{
  "mission_id": "...",
  "decision_id": "DEC-xxxxxxxx",
  "key_claims": [...],
  "attacks_that_materially_mattered": [...],
  "rebuttals_that_materially_mattered": [...],
  "final_verdict": "GO | NO-GO | CONDITIONAL",
  "decision_status": "ENFORCED CONDITIONAL | HUMAN REVIEW REQUIRED | ...",
  "confidence_score": 0-100,
  "score_delta": +/- vs prior similar decision,
  "reusable_pattern_tags": ["infrastructure", "single-point-of-failure", ...]
}
```

**What does NOT get written back:**
- Conversational filler from any model
- Duplicate claims already present in the graph
- Low-signal side chatter
- Temporary reasoning fragments produced during adjudication
- Raw transcript blobs
- Intermediate extraction drafts
- Red Team output verbatim (only the attacks that materially changed the verdict)

---

## Graph Node Structure

```
(Decision)-[:RESOLVED_BY]->(GovernorVerdict)
(Decision)-[:CHALLENGED_BY]->(RedTeamAttack)
(GovernorVerdict)-[:TAGGED_WITH]->(PatternTag)
(Decision)-[:SIMILAR_TO]->(Decision)   ← cross-decision memory
(GovernorVerdict)-[:DOWNGRADED_FROM]->(PriorVerdict)
```

---

## The Loop

```
Neo4j (memory layer)
    ↓ Retrieval packet — high-signal only
Korum (adjudication layer)
    ↓ Extract → Attack → Governor
    ↓ Compare against prior patterns
    ↓ Produce verdict + delta
Neo4j (write-back)
    ↓ Persist durable knowledge objects only
    ↓ Graph grows in quality
Next similar decision
    ↓ Retrieval finds it
    ↓ Korum reasons from precedent, not from scratch
```

---

## Implementation Order (DecisionFormation Lab)

| Priority | Task | Est. Time |
|----------|------|-----------|
| 1 | Governor write-back to Neo4j (`loaders.py`) | 30-45 min |
| 2 | Retrieval query endpoint (`/api/graph/solutions`) | 1-2 hrs |
| 3 | Handoff packet structure (Neo4j → Korum) | 1 hr |
| 4 | Pattern tagging on write-back | 1 hr |
| 5 | Cross-decision similarity links | 2 hrs |
| 6 | Promote to KorumOS after lab validation | TBD |

---

*Every concept proven in DecisionFormation before KorumOS promotion.
Every sharp thing in KorumOS should have a DecisionFormation scar.*
