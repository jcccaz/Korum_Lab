# DecisionFormation — Owner's Manual
**Version:** 1.0 — March 2026
**Purpose:** How to set up, run, and understand this project from zero

---

## What This Is

A 3-layer intelligence lab that takes a messy paragraph of text (an email, a decision memo, a status update) and turns it into a structured, queryable knowledge graph.

**The three layers:**

| Layer | Tool | What it does |
|---|---|---|
| Extraction | OpenAI GPT-4o | Reads unstructured text → forces it into a strict schema |
| Vector Memory | ChromaDB | Stores text as mathematical vectors → find similar decisions by meaning |
| Graph | Neo4j | Stores relationships between entities → answer "why" not just "what" |

You can run each layer independently (step1, step2, step3) or all together (`main.py`).

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
    │   └── extraction.py       The Korum Ontology schema (Pydantic)
    │
    └── graph/
        ├── driver.py           Neo4j singleton connection manager
        ├── schema.py           Creates uniqueness constraints (primary keys)
        ├── loaders.py          Inserts extracted data into the graph
        └── queries.py          Reads/interrogates the graph
```

---

## What to Try Next

1. **Change the sample text in `main.py`** — paste in a real decision memo or status update and see what the graph extracts
2. **Query the graph visually** — run it, then explore http://localhost:7474 with `MATCH (n) RETURN n`
3. **Add a second decision** — run it twice with different text and see the graph grow
4. **Try the semantic search** — run `step2_vector_memory.py` and see how it finds documents by meaning, not keywords

---

*DecisionFormation Lab — korum-os.com*
