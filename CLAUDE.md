# Project Notes — DecisionFormation / Korum Lab

## What this is

A local proving-ground lab (not production KorumOS). Three layers:
extraction (OpenAI GPT-4o) -> vector memory (ChromaDB) -> graph (Neo4j).
Driven via a dashboard ("Korum Lab Console") at `localhost:5173`, backed
by a FastAPI server natively on port 8000 (the one the dashboard actually
talks to — there's also a Dockerized copy on port 8080 that the
dashboard does NOT use).

Full setup/run/troubleshooting procedure: see `OWNER_MANUAL.md` (and its
.docx twin, `DecisionFormation_OwnersManual.docx` — keep both in sync if
you edit one). Read that before touching the Neo4j/Docker startup flow —
it has a step-by-step "Quick Start" section and an error table built
from real failures, not guesses.

## Hot gotchas (read before debugging Neo4j connection issues)

- **Two Neo4j setups exist on this machine and they fight over the same
  port (7687).** Neo4j Desktop has a local instance named "korum-lab"
  (database `korumlab`, real but stale/unused data). Docker has its own
  Neo4j (`decisionformation-neo4j-1`, database `neo4j`). Only one can
  hold port 7687 at a time. If the dashboard's "Graph Engine Status"
  says `Unauthorized` for no obvious reason, check which one is running
  in Neo4j Desktop -> Local instances and stop it if it's not the one
  you mean to use.

- **Neo4j Aura: do NOT assume the username/database is `neo4j`.** This
  account's free Aura instance uses the instance ID (e.g. `56d8ad1d`)
  as *both* `NEO4J_USER` and `NEO4J_DATABASE` — not the standard
  default. A whole night was burned assuming the standard convention
  and "fixing" correct credentials into broken ones. If Aura auth
  fails, verify the actual username/database in the Aura console
  itself before changing anything — don't guess from convention.

- **Stale backend process gotcha:** if the backend terminal shows zero
  new log lines despite the dashboard clearly getting a real response,
  an old `uvicorn` process from a previous run is still alive on port
  8000, answering with whatever `.env` it loaded at its own start time.
  Close every terminal window tied to this project and re-run
  `start_korum.bat` for one clean process before trusting any further
  diagnosis.

- **This sandbox's view of files can go stale mid-edit.** If a file you
  just edited (via Read/Write/Edit tools) shows truncated/wrong content
  when read through the bash tool, don't trust bash's view — re-read
  via the file tools directly, or write to a fresh filename and rename
  over the original to force a resync before running anything (e.g.
  `docx` pack scripts, `git add`) against it.

## Ontology note (in progress, not yet implemented)

Discussed but not built: a first-class **Reversal Trigger** node type
(alongside Evidence/Risk/Assumption/Unknown/Recommendation) — a
condition that, if it later becomes true, should force a decision to
be revisited. Distinguishing test: can it be phrased as "IF [condition]
THEN this decision must be revisited"? If yes, it's a Reversal Trigger,
not a Risk. This would also reframe WATCHTOWER's mission from "monitor
events" to "monitor decision preconditions." Not started — see chat
history for the full reasoning if picked back up.

## Cross-app integration (deferred, documented elsewhere)

A VEIL <-> WorldView bidirectional spatial-event + shared-graph proposal
(from Gemini) was evaluated and explicitly deferred — see Section 8 of
`Korum_Worldview/VEIL_ECOSYSTEM_SPEC.md` for what was actually found
in the real code (separate Railway services, no shared backend, a
dormant one-way bridge already built but unconfigured) before picking
this back up.
