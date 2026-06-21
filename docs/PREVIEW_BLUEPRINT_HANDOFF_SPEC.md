# Spec: Move blueprint preview out of /api/forge namespace

Hand-off spec — three independent build slices. **Codex builds the backend.
Claude builds the frontend. Gemini updates the docs.** Read "Interface
Contract" first regardless of which slice you own — it's the thing that
keeps the three slices compatible without anyone needing to coordinate live.

## Repo & file locations (check this before opening anything)

Everything in this spec lives in **one repo**:

```
C:\Users\carlo\Projects\DecisionFormation
```

Every file below is given as an absolute path. If your working directory is
already `DecisionFormation`, the path relative to repo root is also shown —
use whichever matches how you were invoked, but confirm you're editing the
file at the absolute path, not a same-named file in a different repo (there
is, confusingly, also a `Foundry` repo at `C:\Users\carlo\Projects\Foundry`
with its own `app.py` — that is NOT this repo, do not touch it for this spec).

| Owner | Absolute path | Relative to repo root |
|---|---|---|
| Codex | `C:\Users\carlo\Projects\DecisionFormation\korum_lab\graph\loaders.py` | `korum_lab/graph/loaders.py` |
| Codex | `C:\Users\carlo\Projects\DecisionFormation\korum_lab\graph\queries.py` | `korum_lab/graph/queries.py` |
| Codex | `C:\Users\carlo\Projects\DecisionFormation\api.py` | `api.py` |
| Claude | `C:\Users\carlo\Projects\DecisionFormation\korum-ui\src\KorumDashboard.tsx` | `korum-ui/src/KorumDashboard.tsx` |
| Gemini | `C:\Users\carlo\Projects\DecisionFormation\OWNER_MANUAL.md` | `OWNER_MANUAL.md` |

This spec file itself: `C:\Users\carlo\Projects\DecisionFormation\docs\PREVIEW_BLUEPRINT_HANDOFF_SPEC.md`

## Problem

`POST /api/forge/blueprint` was built under the mistaken assumption that no
Forge existed anywhere. It does — a separate, already-deployed Foundry app
has the real Forge: council seats (Strategic Planner / Product Architect /
Systems Builder / Build Engineer), phased builds, Construction Documents,
and a Send to Coder action. DecisionFormation's endpoint is a single GPT-4o
call with none of that. Living under `/api/forge/` implies it's the build
path. It isn't, and it must stop looking like it is.

## Architectural boundary (context for all three slices — do not implement this part, just respect it)

```
DecisionFormation creates the Concept Lock
        ↓
ANCHOR stores the Concept Lock
        ↓
Foundry's real Forge consumes it as an Active Bearing
        ↓
Foundry produces the canonical Implementation Blueprint
```

Today, the arrow from ANCHOR into Foundry is **manual only** — a human
copies text and pastes it into Foundry's Arena input. There is no import
button on Foundry's side. Nothing in this spec builds that import — this
spec only fixes naming and scope *inside DecisionFormation* so the thing it
already does (a quick sanity-check preview) can't be mistaken for the real
build path.

## What changes, in one sentence

`POST /api/forge/blueprint` (body-driven, "BuildBlueprint", `BLUEPRINTED_AS`)
becomes `POST /api/concept-lock/{lock_id}/preview-blueprint` (no body, reads
the lock fresh from Neo4j, explicitly flagged `is_preview: true`, linked via
`PREVIEWED_AS` instead of `BLUEPRINTED_AS` so that relationship name stays
free for whatever eventually represents Foundry's real Implementation
Blueprint linking back to the same Concept Lock).

---

## Interface Contract (read this before building anything)

**Request:** `POST /api/concept-lock/{lock_id}/preview-blueprint` — no body.
**Request:** `GET /api/concept-lock/{lock_id}/preview-blueprint` — no body.

**Response (both verbs, same shape):**
```json
{
  "id": "BPV-83085b95",
  "lock_id": "LOCK-abc123",
  "status": "PREVIEW",
  "is_preview": true,
  "note": "Test harness preview — not the canonical Forge build. Foundry's real Forge produces the Implementation Blueprint.",
  "product_brief": "...",
  "architecture_blueprint": "...",
  "data_model": ["..."],
  "required_components": ["..."],
  "dependencies": ["..."],
  "build_phases": ["..."],
  "validation_gates": ["..."],
  "graph_status": "Linked into Neo4j Ontology"
}
```

**Errors:**
- `404` if `lock_id` doesn't match any `:ConceptLock` in Neo4j (POST and GET).
- `GET` additionally `404`s if no preview has been generated yet for that lock (don't auto-generate on GET — only POST generates).
- `500` if the LLM call fails (`detail: "Blueprint generation failed: ..."`)..

This is the only contract Codex must produce, Claude must consume, and
Gemini must document. If any of the three needs a field not listed here,
update this section first so the other two stay in sync.

---

## CODEX — Backend (Python / FastAPI / Neo4j)

Repo: `C:\Users\carlo\Projects\DecisionFormation` (NOT the `Foundry` repo)

Files you will edit, by absolute path:
- `C:\Users\carlo\Projects\DecisionFormation\korum_lab\graph\loaders.py`
- `C:\Users\carlo\Projects\DecisionFormation\korum_lab\graph\queries.py`
- `C:\Users\carlo\Projects\DecisionFormation\api.py`

1. **`loaders.py`** — rename `insert_build_blueprint` to `insert_blueprint_preview(tx, lock_id: str, blueprint)`.
   - `lock_id` is now required, not `Optional` — the new route always has a real lock_id from the URL path, so drop the `if lock_id:` guard entirely.
   - `blueprint_id` prefix changes from `"BP-"` to `"BPV-"` (Blueprint Preview) — avoids future ID collisions with whatever Foundry's real Implementation Blueprint ends up being called.
   - Node property `bp.status` is always the literal `'PREVIEW'` (no `status` param) and add `bp.is_preview = true`.
   - Relationship: `MERGE (lock)-[:PREVIEWED_AS]->(bp)`, not `BLUEPRINTED_AS`.

2. **`korum_lab\graph\queries.py`** (`C:\Users\carlo\Projects\DecisionFormation\korum_lab\graph\queries.py`) — add `query_preview_for_lock(tx, lock_id)`:
   ```cypher
   MATCH (lock:ConceptLock {id: $lock_id})-[:PREVIEWED_AS]->(bp:BuildBlueprint)
   RETURN bp.id AS id, bp.product_brief AS product_brief,
          bp.architecture_blueprint AS architecture_blueprint,
          bp.data_model AS data_model, bp.required_components AS required_components,
          bp.dependencies AS dependencies, bp.build_phases AS build_phases,
          bp.validation_gates AS validation_gates, bp.generated_at AS generated_at
   ORDER BY bp.generated_at DESC LIMIT 1
   ```
   Remove `query_build_blueprint` (the old blueprint-id-keyed lookup) once you've confirmed nothing else in `api.py` calls it.

3. **`api.py`** (`C:\Users\carlo\Projects\DecisionFormation\api.py`, repo root — NOT `Foundry\app.py`):
   - Delete `POST /api/forge/blueprint`, `GET /api/forge/blueprint/{blueprint_id}`, the `BlueprintRequest` model, and `_build_blueprint_summary(req)`.
   - Add `POST /api/concept-lock/{lock_id}/preview-blueprint`:
     1. `lock = session.execute_read(query_concept_lock, lock_id)` — 404 if `None`.
     2. Build the LLM prompt summary directly from the `lock` dict's fields (`core_thesis`, `supporting_assumptions`, `risks`, `recommendations`, `open_unknowns`, `decision_conditions`, `required_validations`, `failure_triggers`, `monitoring_requirements` — these come back flat from `query_concept_lock`, no nested object to unwrap). Write a small `_build_preview_summary(lock: dict) -> str` replacing the old Pydantic-based version — same text layout as before is fine.
     3. `blueprint = run_blueprint_generation(summary)` — unchanged, this function doesn't move.
     4. `blueprint_id = session.execute_write(insert_blueprint_preview, lock_id, blueprint)`.
     5. Return the shape in **Interface Contract** above. `note` is a fixed string, not LLM output.
   - Add `GET /api/concept-lock/{lock_id}/preview-blueprint`:
     1. `record = session.execute_read(query_preview_for_lock, lock_id)` — 404 if `None` (don't fall back to generating — that's what POST is for).
     2. Return the same shape, `graph_status: "Loaded from Neo4j"`.
   - `GovernanceConditions` Pydantic model and `PushToAnchorRequest` are untouched — they don't move, they're not part of this slice.

---

## CLAUDE — Frontend

Repo: `C:\Users\carlo\Projects\DecisionFormation` (NOT the `Foundry` repo)

File you will edit, by absolute path:
`C:\Users\carlo\Projects\DecisionFormation\korum-ui\src\KorumDashboard.tsx`

This is a Vite/React app under the `korum-ui` subfolder of the DecisionFormation
repo — if you're invoked with `korum-ui` itself as your working directory,
the file is at `src\KorumDashboard.tsx` relative to where you are; confirm
against the absolute path above either way.

1. `handleGenerateBlueprint`'s `fetch` call changes to:
   ```ts
   fetch(`http://127.0.0.1:8000/api/concept-lock/${conceptLock.id}/preview-blueprint`, { method: "POST" })
   ```
   No body — drop the entire JSON payload that currently sends `core_thesis`, `supporting_assumptions`, etc. The backend now reads the lock fresh from Neo4j by ID.
2. Guard: if `!conceptLock?.id` (the lock exists client-side but Neo4j was offline when it was created, so it never got a real id), disable the button with tooltip `"Preview unavailable — this Concept Lock wasn't persisted (Neo4j was offline when it was locked)."` — distinct from the existing `!conceptLock` disabled state.
3. Relabel, don't just recolor:
   - Section header: `Foundry Workshop Build — "How Would We Build This?"` → `Concept Lock Preview (Test Harness — Not Real Forge)`
   - Button: `Generate Build Blueprint` → `Generate Preview Blueprint`
   - Add a one-line disclaimer under the header, rendered from the response's `note` field once one exists, falling back to a hardcoded string before the first generation: `"Quick sanity check of this Concept Lock's contents — not a build plan. The real build happens in Foundry's Forge."`
4. `BuildBlueprint` interface — add `is_preview: boolean` and `note: string`. Keep `id`/`lock_id`/`status` field names as-is (they match the Interface Contract above).
5. Variable names (`buildBlueprint`, `isGeneratingBlueprint`, `blueprintError`) can stay as-is — this is a relabel of user-facing text and the request shape, not a full rename pass. Don't touch the reset logic in `handleReset` / `handleLoadDecision` / `handleGovernorResolve` / `handleLockConcept` — those already clear this state correctly and aren't affected by the endpoint change.

---

## GEMINI — Docs

Repo: `C:\Users\carlo\Projects\DecisionFormation` (NOT the `Foundry` repo —
that repo has its own, unrelated docs in `Foundry\docs\`)

File you will edit, by absolute path:
`C:\Users\carlo\Projects\DecisionFormation\OWNER_MANUAL.md` (repo root)

1. Replace the "Foundry Workshop Build — Forge MVP (Build Blueprint Generator)" section. The new version must state the **Architectural boundary** (copy the diagram from this spec's top section) before anything else, then describe the preview endpoint with an explicit **"What this is NOT"** callout: not the real Forge, no council seats, no phasing, no Construction Documents, no Send to Coder — a single LLM call that sanity-checks whether the Concept Lock contains enough signal to plan from at all.
2. Note explicitly that the Concept Lock → Foundry handoff is manual-only today (copy the Send-to-ANCHOR markdown fallback, paste into Foundry's Arena) — there is no import button on Foundry's side yet, and this spec doesn't build one.
3. Update the Decision Lifecycle table's row 6: button label `Generate Preview Blueprint`, endpoint `POST /api/concept-lock/{id}/preview-blueprint`.
4. Update the Cypher example: `(:ConceptLock)-[:BLUEPRINTED_AS]->(:BuildBlueprint)` → `(:ConceptLock)-[:PREVIEWED_AS]->(:BuildBlueprint)`.
5. Update the file map's endpoint list block — remove `/api/forge/blueprint` lines, add:
   ```
   POST /api/concept-lock/{id}/preview-blueprint   Test harness — NOT Forge. Preview only.
   GET  /api/concept-lock/{id}/preview-blueprint    Reload the existing preview for a lock.
   ```
6. Update any error-table rows referencing the old button/endpoint name.
7. Bump version to 1.3, "what's new" line: renamed and reframed the blueprint preview to make clear it isn't Foundry's real Forge.

---

## Acceptance test (run after all three slices land — anyone can run this)

1. Lock a Concept (Governor verdict GO or CONDITIONAL) → note its `id`.
2. `POST /api/concept-lock/{id}/preview-blueprint`, no body → `200`, response has `is_preview: true`, `status: "PREVIEW"`, all 7 blueprint fields populated, `note` is the fixed disclaimer string.
3. `GET /api/concept-lock/{id}/preview-blueprint` → same data back, `graph_status: "Loaded from Neo4j"` (confirms it didn't silently regenerate).
4. `GET /api/concept-lock/{a-different-lock-id-with-no-preview-yet}/preview-blueprint` → `404`.
5. In the dashboard: Lock Concept → "Generate Preview Blueprint" enabled → click → panel shows the disclaimer line + all 7 fields.
6. `grep -ri "forge/blueprint" OWNER_MANUAL.md api.py korum-ui/src/KorumDashboard.tsx` → no matches anywhere.
7. Old routes are gone, not dead code left registered — `/api/forge/blueprint` should 404 as an unknown route, not exist disabled.
