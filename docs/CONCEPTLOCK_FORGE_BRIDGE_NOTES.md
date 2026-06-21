# ConceptLock → Foundry Forge bridge — DEFERRED (pending test)

**Status:** Not built. Deliberately deferred. We are running a test first to see
whether an automated bridge is even needed before investing in it. Do **not**
build this until the test shows it's warranted.

_Captured 2026-06-20 while tracing the korum_lab → ANCHOR → Foundry pipeline._

## The pipeline as it actually exists today

```
KORUM LAB console (korum-ui, localhost:5173)
        →  :Decision graph in Neo4j
           (Decision + Project + Evidence + Assumption + Risk + Unknown +
            Recommendation + Strategy — written by korum_lab/graph/loaders.py)
        →  Lock Concept   →  :ConceptLock node   (d)-[:LOCKED_AS]->(lock)
        →  Preview Blueprint →  (lock)-[:PREVIEWED_AS]->(:BuildBlueprint)
                                 ⚠ test-harness sanity check ONLY — NOT Forge
        →  [MANUAL] copy text → paste into Foundry ARENA input
        →  council synthesis → Active Bearing → FORGE (Build & Execute)  ← real build
```

## Why the handoff is manual today

- Foundry's Forge build endpoint is `POST /api/workshop`
  (`Foundry/app.py:2694`). It **hard-requires a `bearing` string**
  (`app.py:2700`, rejected at `:2710` if empty).
- The only producer of a Bearing in Foundry's UI is the Arena council
  (`POST /api/arena`, `Foundry/app.py:1739`), which writes
  `#workshopBearingDisplay` (the "Active Bearing" strip).
- There is **no import / anchor-pull / load-from route** anywhere in
  `Foundry/app.py`. A `:Decision` / `:ConceptLock` cannot reach Forge except by
  a human pasting its substance into the Arena textarea (`#arenaInput`,
  `Foundry/templates/index.html:4256`).
- A korum_lab `:Decision` graph is **not** a Bearing — different artifact, different
  stage. Foundry re-synthesizes pasted text into a Bearing; it does not execute a
  premade blueprint verbatim.

## What the bridge would be (IF the test says we need it)

A net-new feature spanning two apps:
1. **Foundry-side import route** — e.g. `POST /api/arena/from-anchor` (or
   `/from-concept-lock`) that accepts a ConceptLock payload, maps its
   `core_thesis` (+ key assumptions/risks/recommendations) into the `bearing`
   field, and seeds the Active Bearing — optionally skipping the Arena council,
   optionally still running it.
2. **A "Load from ANCHOR" control** on Foundry's Arena tab so the operator picks
   a stored ConceptLock instead of copy-pasting.
3. (Optional) Direct `:ConceptLock` → `/api/workshop` path if we decide Forge
   should build straight from the lock without a council re-pass.

This is explicitly **out of scope** of the PREVIEW_BLUEPRINT_HANDOFF_SPEC, which
fixed only naming/scope inside DecisionFormation and confirmed the ANCHOR→Foundry
arrow is manual-only by design for now.

## The open question the test should answer

Does pasting the ConceptLock text into the Arena (and letting the council
re-synthesize it) produce a good-enough Bearing on its own? If yes, the bridge is
a convenience at best and may not be worth building. If the manual re-synthesis
loses fidelity or the operator wants the lock executed verbatim, that's the
signal to build the bridge.
