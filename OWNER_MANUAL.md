# DecisionFormation — Owner's Manual
**Version:** 1.3 — June 2026
**Purpose:** How to set up, run, and understand this project from zero

**What's new in 1.3:** renamed and reframed the blueprint preview to make clear it isn't Foundry's real Forge.

**What's new in 1.2:** a **Generate Build Blueprint** step — Forge MVP —
that turns a locked Concept Lock into planning artifacts (Product Brief,
Architecture Blueprint, Data Model, Required Components, Dependencies,
Build Phases, Validation Gates). Deliberately scoped to planning only:
no code, no repo, no deployment. See "Concept Lock Preview" below.

**What's new in 1.1:** the dashboard now has a **History** panel (reload
past extractions from Neo4j), a **Lock Concept** step that freezes a
Council-approved decision into a reusable institutional pattern, and a
**Send to ANCHOR** button that archives that locked pattern — not the raw
decision — into ANCHOR's long-term memory. See "The Decision Lifecycle"
and "Concept Locks" below.

---

## What This Is

A 3-layer intelligence lab that takes a messy paragraph of text (an email, a decision memo, a status update) and turns it into a structured, queryable knowledge graph.

**The three layers:**

| Layer | Tool | What it does |
|---|---|---|
| Extraction | OpenAI GPT-4o | Reads unstructured text → forces it into a strict schema |
| Vector Memory | ChromaDB | Stores text as mathematical vectors → find similar decisions by meaning |
| Graph | Neo4j | Stores relationships between entities → answer "why" not just "what" |

You can run each layer independently (step1, step2, step3) or all together (`main.py`). There's also a dashboard (see "Quick Start — Dashboard Workflow" below) that drives all three layers from a browser UI instead of the command line.

---

## Quick Start — Dashboard Workflow (the way this is actually used day to day)

This is the procedure for booting up the lab locally. Everything runs on
your own machine — you should never need to visit Neo4j's website or
sign in to anything online for this.

### Before you start: only one Neo4j may be running

This machine has **two separate local Neo4j setups** that both want the
same port (7687):

1. **Docker** (`decisionformation-neo4j-1`, via `docker-compose.yml`) —
   this is the one the app is actually configured to use. Credentials:
   `neo4j` / `korumlab123`, database `neo4j`.
2. **Neo4j Desktop** (an instance named "korum-lab", with a database
   literally called `korumlab`) — this is the *original* setup from
   months ago. It still exists with real data in it, but the app no
   longer points at it.

Only one of these can hold port 7687 at a time. **Before launching,
open Neo4j Desktop and make sure the "korum-lab" instance is STOPPED.**
If it's left running, the dashboard will fail with a Neo4j
"Unauthorized" error that has nothing to do with your actual password —
it's just talking to the wrong Neo4j.

### Startup steps

1. Open **Docker Desktop** and wait for it to fully start.
2. Check **Neo4j Desktop → Local instances** — if "korum-lab" shows
   RUNNING, stop it.
3. Double-click **`start_korum.bat`** in this folder. It opens three
   windows and spins up:
   - Neo4j + the FastAPI backend, in Docker (`docker-compose up -d`)
   - The Python API natively, on `http://127.0.0.1:8000`
   - The Vite dashboard, on `http://localhost:5173`
4. Open `http://localhost:5173` — that's the dashboard ("Korum Lab
   Console"). Paste in a decision scenario and click **Extract
   Insights**, then optionally **Red Team Attack** → **Governor
   Resolve** → **Lock Concept** → **Send to ANCHOR** / **Push to
   KorumOS** / **Generate Preview Blueprint**. Full walkthrough of what
   each button does and when it's available: see "The Decision
   Lifecycle" below.
5. To see the actual graph: open `http://localhost:7474/browser/`
   **by typing that exact address** — don't search "Neo4j" and click
   into the marketing site, you want your own local instance, not
   Neo4j Aura. Log in with `neo4j` / `korumlab123` (database `neo4j`),
   then run:
   ```cypher
   MATCH (n)-[r]->(m) RETURN n, r, m LIMIT 100
   ```

### How to tell if it actually worked

After running Extract Insights, scroll to the very bottom of the
results panel on the dashboard — there's a **"Graph Engine Status"**
line. That's the real signal:
- `Injected into Neo4j Ontology` → it worked, the graph updated.
- `Offline / Bypass active (... Unauthorized ...)` → wrong Neo4j is
  running, see the port-conflict note above.

---

## The Decision Lifecycle (Dashboard Button Flow)

Every button on the dashboard maps to one API endpoint and one stage of
the KORUM Concept Lock Workflow. Buttons are gated in order — most won't
do anything (or won't even be enabled) until the step before it has run.

| # | Button | Calls | What happens | Gated by |
|---|---|---|---|---|
| 0 | **History** (top right) | `GET /api/decisions` → `GET /api/decisions/{id}` | Lists past decisions read back out of Neo4j; click one to reload it into the results panel | Nothing — always available |
| 1 | **Extract Insights** | `POST /api/extract` | GPT-4o turns your pasted text into Project / Decision / Evidence / Assumptions / Risks / Unknowns / Recommendation, scores confidence, writes a `:Decision` node to Neo4j | Some text in the input box |
| 2 | **Red Team Attack** | `POST /api/rebuttal` | Local Mistral 7B argues against the extracted decision — finds holes, missing evidence, weak assumptions | A successful extraction |
| 3 | **Governor Resolve** | `POST /api/governor` | 3-step arbitration (rule checks → GPT-4o ruling → hard caps/overrides) issues a final **GO / NO-GO / CONDITIONAL** verdict with adjusted confidence | A completed Red Team attack |
| 4 | **Lock Concept** | `POST /api/concept-lock` | Freezes the verdict into a Concept Lock — see next section. **Disabled on NO-GO** | A Governor verdict that isn't NO-GO |
| 5a | **Send to ANCHOR** | `POST /api/push-to-anchor` | Archives the *locked* Concept Lock into ANCHOR's institutional memory | A Concept Lock must exist — button stays disabled (with a tooltip) until you lock |
| 5b | **Push to KorumOS** | `POST /api/push-to-korum` | Hands the Governor's verdict to the separate KorumOS Neural Council for deeper execution planning. Independent of locking — this is a different system, not part of the Concept Lock chain | A Governor verdict |
| 6 | **Generate Preview Blueprint** | `POST /api/concept-lock/{id}/preview-blueprint` | Concept Lock Preview — sanity checks whether the Concept Lock contains enough signal to plan from at all. **Test harness only — not Forge** — see "Concept Lock Preview" below | A Concept Lock must exist — same gating as Send to ANCHOR |

Re-running **Governor Resolve** (e.g. after a second rebuttal round)
clears any existing Concept Lock *and* any Preview Blueprint generated
from it — a stale lock (or a preview built from a stale lock) against
an old verdict would be worse than having neither, so both reset
together and you redo the chain against the new ruling. Re-locking the
concept (without re-running Governor Resolve) also clears any existing
preview, for the same reason.

---

## Concept Locks — What They Are and Why

Per the KORUM Concept Lock Workflow, the point of this whole pipeline
**is not to store decisions** — Neo4j already does that the moment you
click Extract. The point is to capture *the reasoning that produced an
approved architecture*, frozen into something Foundry and ANCHOR can
reuse later as an institutional pattern, not a one-off report.

A Concept Lock has six parts:

| Field | Answers | Built from |
|---|---|---|
| **Core Thesis** | What was decided, for what project, and why | `project` + `decision_context` + `recommendation` |
| **Supporting Assumptions** | What was believed without hard proof | The original extraction's `assumptions` |
| **Risks** | What could go wrong | Original `risks`, **deduplicated** against any net-new risks the Red Team surfaced |
| **Recommendations** | The course of action taken | The original `recommendation` |
| **Open Unknowns** | What's still unconfirmed | The original `unknowns` |
| **Governance Conditions** | See below — kept as 4 separate lists, not one | Governor's verdict fields |

**Governance Conditions are deliberately split into four subfields, never
flattened into one list**, because each answers a different question for
a different downstream consumer:

| Subfield | Question it answers | Who consumes it |
|---|---|---|
| `decision_conditions` | What must be true to approve this? | The approval gate itself |
| `required_validations` | What must be checked before execution? | Foundry Build (pre-execution gate) |
| `failure_triggers` | What would force reversal or review? | Foundry Build (reversal hook) |
| `monitoring_requirements` | What must be watched on an ongoing basis? | Watchtower (live monitoring hook) |

**A NO-GO can never be locked.** `POST /api/concept-lock` returns
`400 Cannot lock a NO-GO decision` if you try — a rejected decision is a
dead end, not a reusable pattern, and locking it would pollute
institutional memory with patterns that were specifically *not*
approved. GO locks as `status: "LOCKED"`; CONDITIONAL locks as
`status: "CONDITIONAL_LOCK"` (still a pattern worth keeping, just one
with conditions attached).

In Neo4j, a lock is its own node type — `:ConceptLock` — linked back to
its source `:Decision` via `(:Decision)-[:LOCKED_AS]->(:ConceptLock)`.
The four Governance Conditions subfields are stored as four separate
list properties on that node (Neo4j has no nested-map property type, so
storing them as one structured object isn't possible at the storage
layer — the API reassembles them into the nested shape on the way out).

**What's built vs. what's still conceptual:** this manual covers stages
1–6 of the full documented workflow (Foundry exploration → Council →
Governance Graph → Concept Lock → ANCHOR → Concept Lock Preview). Stage
6 is intentionally narrow right now — see "Concept Lock Preview" below.
Stage 7, Forge actually executing a blueprint (repo generation, QA gates,
deployment), is described in `KorumOS/docs/FOUNDRY_FORGE_TOMORROW.md` but
doesn't exist as working code yet — and won't, until the narrower
handoff this stage tests proves out repeatedly.

---

## Concept Lock Preview (Test Harness — Not Real Forge)

**Architectural Boundary:**
```
DecisionFormation creates the Concept Lock
        ↓
ANCHOR stores the Concept Lock
        ↓
Foundry's real Forge consumes it as an Active Bearing
        ↓
Foundry produces the canonical Implementation Blueprint
```

**What this is NOT:** This preview is **not the real Forge**. It has no council seats, no phasing, no Construction Documents, and no Send to Coder. It is simply a single LLM call that sanity-checks whether the Concept Lock contains enough signal to plan from at all. 

**Manual Handoff:** The Concept Lock → Foundry handoff is **manual-only** today. To import a Concept Lock into Foundry, you must copy the Send-to-ANCHOR markdown fallback and paste it into Foundry's Arena. There is no import button on Foundry's side yet.

**Input** (from the locked Concept Lock): Core Thesis, Supporting
Assumptions, Risks, Recommendations, Governance Conditions (all four
subfields).

**Output** — a Preview Blueprint with seven fields:

| Field | What it captures |
|---|---|
| **Product Brief** | What's being built, for whom, and why — grounded in the Concept Lock, not a generic pitch |
| **Architecture Blueprint** | The major pieces and how they relate, in prose — not code |
| **Data Model** | Key entities/structures, conceptually — not SQL/Cypher |
| **Required Components** | Services/modules/pieces that must exist |
| **Dependencies** | External libraries, APIs, infrastructure, other KORUM systems (ANCHOR, Watchtower) |
| **Build Phases** | An ordered sequence — sequence matters |
| **Validation Gates** | What must pass before the next phase, informed by but not identical to the lock's Governance Conditions |

In Neo4j, a preview blueprint is its own node type — `:BuildBlueprint` — linked
back to the Concept Lock it was generated from via
`(:ConceptLock)-[:PREVIEWED_AS]->(:BuildBlueprint)`. Status is set to
`PREVIEW`.

---

## ANCHOR Integration

"Send to ANCHOR" archives a locked Concept Lock into ANCHOR's
institutional memory via ANCHOR's own service-to-service endpoint,
`POST /api/anchor/ingest` (Bearer-key auth, no browser session).

**Setup — two env vars in `.env`:**
```
ANCHOR_URL=          # wherever your anchor-runtime instance is reachable, local or cloud
ANCHOR_API_KEY=      # must match ANCHOR_API_KEY configured on the anchor-runtime server
```

**If `ANCHOR_API_KEY` isn't set**, Send to ANCHOR doesn't fail — it
returns `status: "manual_required"` with the fully rendered Concept Lock
package and a **Copy Package** button, so you can paste it into ANCHOR
by hand. Same fallback pattern as Push to KorumOS.

**What lands in ANCHOR:** the Concept Lock's markdown rendering (Core
Thesis, Supporting Assumptions, Risks, Recommendations, Open Unknowns,
and all four Governance Conditions subsections, each labeled with what
question it answers), tagged `source: "korum"`, `entry_type:
"concept_lock"`, routed into ANCHOR's `korum_decisions` collection so it
counts toward ANCHOR's decision telemetry alongside everything else
KORUM contributes.

---

## Prerequisites — Install These First

### 1. Docker Desktop
Neo4j runs in a Docker container. You need Docker running before any graph work.

Download: https://www.docker.com/products/docker-desktop/

After install, open Docker Desktop and make sure it shows "Running" in the bottom left.

### 2. Python 3.10+
Check your version:
```bash
python --version
```

### 3. OpenAI API Key
You need an API key from https://platform.openai.com/api-keys

Set it in your terminal before running anything:
```bash
# Windows PowerShell
$env:OPENAI_API_KEY="sk-your-key-here"

# Windows CMD
set OPENAI_API_KEY=sk-your-key-here
```

---

## One-Time Setup

### Step 1 — Create a virtual environment
```bash
cd c:\Users\carlo\Projects\DecisionFormation
python -m venv venv
venv\Scripts\activate
```

You'll see `(venv)` appear in your terminal — that means it's active.

### Step 2 — Install dependencies
```bash
pip install -r requirements.txt
```

This installs: OpenAI, Pydantic, ChromaDB, Neo4j driver.

### Step 3 — Start Neo4j (the graph database)
```bash
docker-compose up -d
```

The `-d` flag runs it in the background. First time will download the Neo4j image (~500MB).

**Verify it's running:**
```bash
docker-compose ps
```
You should see `neo4j` with status `Up`.

**Visual check — open the Neo4j browser:**
Go to: http://localhost:7474

Login with:
- Username: `neo4j`
- Password: `korumlab123`

You'll see an empty graph. That's correct — nothing has been loaded yet.

---

## Running the Project

### Option A — Run everything at once (recommended first run)
```bash
python -m korum_lab.main
```

This runs all 4 stages in sequence:
1. Extracts structure from a sample decision text
2. Creates graph constraints (uniqueness rules)
3. Loads the extracted data into Neo4j
4. Queries the graph and prints results

**Expected output:**
```
===== KORUM LAB: FULL ORCHESTRATION COMPLETED =====

[Stage 1] Extracting Unstructured Intelligence...
 -> Found Project: Project Apollo
 -> Found Decision: Whether to roll back to the legacy database or push through the weekend

[Stage 2] Enforcing Database Constraints (Primary Keys)...

[Stage 3] Loading Extracted Decision into the Graph Ontology...
 -> Nodes and relationship edges created based on Korum rules.

[Stage 4] Interrogating the Decision Graph...

-- Query 1: What are all the risks affecting Project Apollo?
   ► Risk to Project Apollo: Losing 12 hours of user activity logs if rollback occurs
   ► Risk to Project Apollo: ...

-- Query 2: What is the exact foundation driving the Apollo decision?
   ► Context: Whether to roll back or wait for the vendor patch
       ✅ Evidence:    Database logs show excessive timeout errors; ...
       ⚠️ Assumptions: The vendor patch will arrive by Friday; ...
       ❓ Unknowns:    Whether the patch covers the clustered database version

[✔] Orchestration Complete.
```

---

### Option B — Run steps individually

#### Step 1 — Extraction only (no Docker needed)
```bash
python step1_extraction.py
```
Takes a hardcoded sample text → calls GPT-4o → prints structured JSON.
Tests that your OpenAI key works and structured extraction is functioning.

#### Step 2 — Vector Memory (no Docker needed)
```bash
python step2_vector_memory.py
```
Ingests 3 sample documents into ChromaDB, then runs 2 semantic search queries.
A folder called `chroma_db/` will be created in the project directory — that's the vector database persisting to disk.

#### Step 3 — Graph only (Docker required)
```bash
python step3_graph_logic.py
```
Connects to Neo4j, creates a simple ontology (Carlos → Korum Lab → Defensible Decisions → Evidence), and queries it.
After running, refresh the Neo4j browser at http://localhost:7474 and type:
```cypher
MATCH (n) RETURN n
```
You'll see your nodes and relationships as a visual graph.

---

## Understanding the Output

### What "nodes" and "relationships" mean

Think of it like this:
- A **node** is a thing: `Project`, `Decision`, `Risk`, `Evidence`, `Assumption`, `Unknown`, `Recommendation`
- A **relationship** is how things connect: `REQUIRES_DECISION`, `SUPPORTED_BY`, `CARRIES_RISK`, `AFFECTS`

When you run `main.py` on the Apollo migration text, the graph it creates looks like:

```
[Project: Apollo] --REQUIRES_DECISION--> [Decision: Roll back or wait?]
                                                  |
                              +-------------------+-------------------+
                              |                   |                   |
                    SUPPORTED_BY           DEPENDS_ON            LIMITED_BY
                              |                   |                   |
                    [Evidence:          [Assumption:          [Unknown:
                    Timeout errors]     Patch arrives Fri]    Covers cluster?]

[Decision] --CARRIES_RISK--> [Risk: Lose 12hr logs] --AFFECTS--> [Project: Apollo]
```

This is why the German architect talks about "defensible decisions" — you can walk backwards from any decision and see exactly what evidence supported it, what assumptions it depended on, and what was unknown at the time.

### The Korum Ontology (the rules)

The schema in `korum_lab/models/extraction.py` defines what the LLM is *allowed* to extract. If it's not in the schema, it can't enter the graph. This is the "graph defines what can exist" principle:

```python
class ExtractedDecision(BaseModel):
    project: str          # The project name
    decision_context: str # The core decision being faced
    evidence: List[str]   # Hard facts — things that are proven
    assumptions: List[str]# Beliefs held without proof
    unknowns: List[str]   # Critical missing information
    risks: List[str]      # What could go wrong
    recommendation: str   # The suggested action
```

Every piece of unstructured text must be forced into this shape before it enters the system.

---

## Querying the Graph Manually

After running `main.py`, open http://localhost:7474 and try these Cypher queries:

**See everything:**
```cypher
MATCH (n) RETURN n LIMIT 50
```

**Find all risks for a project:**
```cypher
MATCH (p:Project {name: 'Project Apollo'})<-[:AFFECTS]-(r:Risk)
RETURN p.name, r.detail
```

**Reconstruct the decision foundation:**
```cypher
MATCH (p:Project)-[:REQUIRES_DECISION]->(d:Decision)
OPTIONAL MATCH (d)-[:SUPPORTED_BY]->(e:Evidence)
OPTIONAL MATCH (d)-[:DEPENDS_ON]->(a:Assumption)
OPTIONAL MATCH (d)-[:LIMITED_BY]->(u:Unknown)
RETURN d.context, collect(e.detail), collect(a.detail), collect(u.detail)
```

**Find all assumptions across all decisions:**
```cypher
MATCH (d:Decision)-[:DEPENDS_ON]->(a:Assumption)
RETURN d.context AS decision, a.detail AS assumption
```

**See every Concept Lock and the decision it was frozen from:**
```cypher
MATCH (d:Decision)-[:LOCKED_AS]->(lock:ConceptLock)
RETURN lock.id, lock.status, lock.core_thesis, d.id AS source_decision
ORDER BY lock.locked_at DESC
```

**Pull a lock's full Governance Conditions (all 4 subfields):**
```cypher
MATCH (lock:ConceptLock {id: $lock_id})
RETURN lock.decision_conditions, lock.required_validations,
       lock.failure_triggers, lock.monitoring_requirements
```

**Trace a Decision all the way through to its Preview Blueprint:**
```cypher
MATCH (d:Decision)-[:LOCKED_AS]->(lock:ConceptLock)-[:PREVIEWED_AS]->(bp:BuildBlueprint)
RETURN d.id AS decision, lock.id AS lock, bp.id AS blueprint,
       bp.product_brief, bp.build_phases
```

---

## Stopping and Restarting

**Stop Neo4j (keeps data):**
```bash
docker-compose stop
```

**Start it again:**
```bash
docker-compose start
```

**Wipe everything and start fresh:**
```bash
docker-compose down -v
docker-compose up -d
```

**ChromaDB (vector memory) lives in the `chroma_db/` folder. To wipe it:**
```bash
# Delete the folder manually or:
rm -rf chroma_db/
```

---

## Common Errors

| Error | Cause | Fix |
|---|---|---|
| `Could not connect to Neo4j` | Docker not running | Open Docker Desktop, run `docker-compose up -d` |
| `OPENAI_API_KEY not set` | Env var missing | Set it in your terminal (see Prerequisites) |
| `ModuleNotFoundError: neo4j` | Dependencies not installed | Run `pip install -r requirements.txt` |
| `ClientError: Schema operations` | Old code bug (fixed) | Already patched in audit |
| Port 7474 not reachable | Neo4j still starting | Wait 30 seconds, try again |
| Dashboard's Graph Engine Status says `Unauthorized` | Neo4j Desktop's "korum-lab" instance is running and holding port 7687 instead of Docker's Neo4j | Stop "korum-lab" in Neo4j Desktop → Local instances, then re-run `start_korum.bat` |
| `docker-compose.yml: ... .env: line N: key cannot contain a space` | A line in `.env` has a key with a space in it (e.g. `foundry api key=...`) | Rename the key to a valid env-var format, e.g. `FOUNDRY_API_KEY=...` (no spaces) |
| `Neo.ClientError.Statement.UnsupportedAdministrationCommand` on `CREATE DATABASE` | Community Edition only supports the default `neo4j` database — multiple databases are an Enterprise feature | Don't create new databases; use `NEO4J_DATABASE=neo4j` in `.env`, not a custom name |
| Backend terminal shows no log lines even though the dashboard got a real response | An old backend process from a previous run is still alive on port 8000, answering with stale settings | Close every terminal window (PowerShell/cmd) tied to this project, then re-run `start_korum.bat` for a clean single process |
| `400 Cannot lock a NO-GO decision` from `/api/concept-lock` | Working as intended — NO-GO decisions aren't reusable patterns and can't be locked | If you believe it should be GO/CONDITIONAL, re-run Governor Resolve with stronger evidence/rebuttal, don't try to force the lock |
| "Send to ANCHOR" button stays disabled / grayed out | No Concept Lock exists yet for this decision | Click **Lock Concept** first — ANCHOR stores approved patterns, not raw decisions |
| Send to ANCHOR returns `status: "manual_required"` | `ANCHOR_API_KEY` isn't set in `.env` | Either set `ANCHOR_URL` + `ANCHOR_API_KEY` (must match the key configured on anchor-runtime), or click **Copy Package** and paste it into ANCHOR manually |
| Send to ANCHOR returns `504` / timeout | anchor-runtime isn't running at `ANCHOR_URL`, or it's unreachable | Start/check anchor-runtime; the Concept Lock package is still returned so nothing is lost — copy and paste it manually if needed |
| History panel shows "History unavailable — is Neo4j running?" | Same Neo4j port-conflict issue as above, or Docker isn't up | Check Docker Desktop + Neo4j Desktop's "korum-lab" instance per the Quick Start section |
| "Generate Preview Blueprint" button stays disabled / grayed out | No Concept Lock exists yet for this decision | Click **Lock Concept** first — previews are generated from approved patterns, not raw decisions |
| `500 Blueprint generation failed` from `/api/concept-lock/{id}/preview-blueprint` | Usually an OpenAI API error (rate limit, key issue) surfacing through `run_blueprint_generation` | Check the same `OPENAI_API_KEY` setup as Extract Insights — it's the same client/model |
| Preview Blueprint fields read like a generic pitch, not specific to your Concept Lock | The Concept Lock itself was thin (vague Core Thesis, few assumptions/risks) — the blueprint generator can only ground itself in what the lock actually contains | Go back further upstream: provide richer original text at Extract Insights so the Decision → Concept Lock has real substance to build from |

---

## File Map

```
DecisionFormation/
│
├── docker-compose.yml          Neo4j container config (username/password/ports)
├── requirements.txt            All Python dependencies
├── OWNER_MANUAL.md             This file
│
├── step1_extraction.py         Standalone: OpenAI structured extraction
├── step2_vector_memory.py      Standalone: ChromaDB vector store + search
├── step3_graph_logic.py        Standalone: Neo4j graph + simple ontology
│
└── korum_lab/                  Modular package (production-style architecture)
    ├── config.py               Connection config (reads from env vars)
    ├── extractor.py            OpenAI extraction call
    ├── main.py                 Full orchestration (runs all 4 stages)
    │
    ├── models/
    │   ├── extraction.py       The Korum Ontology schema (Pydantic)
    │   ├── governor.py         GovernorVerdict schema (Pydantic)
    │   └── blueprint.py        BuildBlueprint schema — Forge MVP (Pydantic)
    │
    └── graph/
        ├── driver.py           Neo4j singleton connection manager
        ├── schema.py           Creates uniqueness constraints (primary keys)
        ├── loaders.py          Inserts decisions + Concept Locks + Build Blueprints into the graph
        └── queries.py          Reads/interrogates the graph (decisions, concept locks, blueprints)
```

**`api.py` (FastAPI backend, not shown above — lives at the repo root)
endpoints, in lifecycle order:**

```
POST /api/extract             Stage 1 — extraction + confidence scoring + graph write
GET  /api/decisions            History — list past decisions
GET  /api/decisions/{id}       History — reload one decision's full detail
POST /api/rebuttal             Stage 2 — Red Team attack (local Mistral 7B)
POST /api/governor             Stage 3 — 3-step Governor arbitration
POST /api/concept-lock          Stage 4 — freeze verdict into a Concept Lock
GET  /api/concept-lock/{id}     Reload one Concept Lock's full detail
POST /api/push-to-anchor        Stage 5 — archive the locked Concept Lock into ANCHOR
POST /api/concept-lock/{id}/preview-blueprint   Test harness — NOT Forge. Preview only.
GET  /api/concept-lock/{id}/preview-blueprint    Reload the existing preview for a lock.
POST /api/push-to-korum         (Separate) hand verdict to KorumOS Neural Council
```

---

## What to Try Next

1. **Change the sample text in `main.py`** — paste in a real decision memo or status update and see what the graph extracts
2. **Query the graph visually** — run it, then explore http://localhost:7474 with `MATCH (n) RETURN n`
3. **Add a second decision** — run it twice with different text and see the graph grow
4. **Try the semantic search** — run `step2_vector_memory.py` and see how it finds documents by meaning, not keywords

---

*DecisionFormation Lab — korum-os.com*
