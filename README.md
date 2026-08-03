# SmartReco — Behavioral AI Recommendation Agent

SmartReco is a course-marketplace web app that watches how each user behaves and generates
personalized, **persuasive**, **catalog-grounded** course recommendations with an agentic
RAG workflow. It's not a "related products" widget: a LangGraph agent observes a user's
tracked activity, reasons about their interests, retrieves the most relevant courses from a
vector database, self-grades and refines the retrieval, reranks the results, and writes a
convincing narrative tailored to that specific user — refreshing as their behavior evolves,
and (bonus) delivering a daily digest email.

All LLM and embedding calls route through **Mesh API** (an OpenAI-compatible gateway).

---

## What's implemented

**Core**
- **Auth & roles** — email/password with bcrypt hashing and a signed session cookie. Two
  roles: `user` (browses, gets recommendations) and `admin` (manages the catalog).
- **Product management with dual-write** — admin CRUD writes every change to **both** SQLite
  (source of truth) **and** Chroma (vector index), kept in sync on create/update/**delete**,
  with a `vector_sync_status` flag and a reconciliation path for durability.
- **Behavioral event tracking** — a non-blocking JS tracker batches events and flushes on a
  size threshold, an idle timer, or page-hide via `navigator.sendBeacon`. High-frequency
  signals (time-on-page, search typing) are pre-aggregated/debounced client-side. The server
  ingests batches with a single bulk insert and returns `204` immediately.
- **Agentic recommendation engine** — a LangGraph agent grounded in real catalog retrieval
  (RAG). Recommendations are stored and refreshed via **smart triggering**: not on every
  event, but gated by an event-count threshold + cooldown, with a max-staleness backstop and
  a served cache in between (no redundant LLM calls).

**All four bonus features**
- ⭐ **Structured agent framework (LangGraph)** — an explicit reasoning graph:
  `analyze_activity → retrieve → grade_retrieval → (refine_query loop) → rerank → generate_copy`.
- ⭐ **Scheduled proactive delivery (APScheduler)** — a daily afternoon digest email reusing
  the exact same recommendation code path as the web route; SMTP with a console-log fallback.
- ⭐ **Observability (LangSmith)** — tracing wired into the agent; every node and LLM call is
  inspectable end-to-end when enabled.
- ⭐ **Retrieval polish** — Chroma **metadata filtering** (category / price) plus an
  **LLM reranking** step over the initial similarity results, and a grade→refine loop that
  broadens weak queries.

---

## Architecture

```
Browser (Jinja2 templates + tracker.js)
   │  batched events (fetch keepalive / sendBeacon)
   ▼
FastAPI
   ├─ routers/        auth · pages · admin_products · events · recommendations
   ├─ services/
   │    ├─ product_service   ── dual-write ──►  SQLite (source of truth)
   │    │                                  └─►  Chroma (vector index)
   │    ├─ event_service     ── bulk insert ─►  SQLite (events)
   │    ├─ mesh_client       ── embeddings/chat ─►  Mesh API
   │    └─ recommendation_service  ◄── shared entrypoint ──┐
   ├─ agent/ (LangGraph)                                   │ (same path)
   │    analyze_activity → retrieve → grade → refine⟲ → rerank → generate_copy
   │            │ Mesh (LLM)      │ Mesh (embed) + Chroma query (+metadata filter)
   └─ scheduler/ (APScheduler)  daily_digest_job ──────────┘  → email_service (SMTP/console)
                                reconcile_job → repairs dual-write drift
```

**Data model** (`app/models/`)
- `users` — id, email, password_hash, role, created_at.
- `products` — id (= Chroma doc id), title, description, category, price, level, `is_active`
  (soft delete), `vector_sync_status`, timestamps.
- `events` — id, user_id (nullable/anonymous), event_type, product_id, payload (JSON),
  session_id, created_at; composite index `(user_id, created_at)`.
- `recommendations` — one row per user (updated in place): narrative, product_ids (JSON),
  retrieval_debug (JSON audit trail), generated_at, event_count_at_generation, status.

### Key design decisions
- **Dual-write consistency**: SQL commits first, then the Chroma write is attempted. A vector
  failure is logged and flags the row `failed` rather than rolling back the primary write —
  SQL is the source of truth, the vector store is a derived index repaired by
  `scripts/reconcile_vector_store.py` (also a periodic job). Deletes are **soft** so event/
  recommendation foreign keys stay valid; the vector entry is removed.
- **Grounding**: the agent is prompted only with real retrieved candidates, and any product id
  the LLM returns is validated against that candidate set — recommendations can never be
  fabricated.
- **Efficiency**: embeddings are computed explicitly through Mesh (not Chroma's default) so the
  query and document sides use the same model; the LLM is gated behind trigger thresholds and a
  cache; events are batched on both client and server.
- **One-row-per-user recommendations** (vs. a history table) is a deliberate simplification;
  the `retrieval_debug` blob + LangSmith traces cover auditability.

---

## Setup & run

Requires Python 3.11+ and a funded **Mesh API** key (embeddings are a paid Mesh model — usage
is tiny, ~$0.02 / 1M tokens).

```bash
# 1. Install
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Configure — copy the template and fill in MESH_API_KEY
cp .env.example .env
#   edit .env: set MESH_API_KEY=rsk_...  (and optionally SMTP / LangSmith)

# 3. Initialize the DB + bootstrap admin, then seed the catalog (real dual-write to Chroma)
python -m scripts.init_db
python -m scripts.seed_products

# 4. Run
uvicorn app.main:app --reload
#   → http://127.0.0.1:8000
```

Log in as the admin from `.env` (`BOOTSTRAP_ADMIN_EMAIL` / `BOOTSTRAP_ADMIN_PASSWORD`) to
manage products at `/admin/products`, or register a user, browse the catalog, and open
**For You** (`/recommendations`).

### Configuration (`.env`)
| Variable | Purpose |
|---|---|
| `MESH_API_KEY` | **Required.** Mesh key (`rsk_...`); all LLM/embedding calls go through it. |
| `MESH_CHAT_MODEL` / `MESH_EMBEDDING_MODEL` | Model ids, e.g. `openai/gpt-4o-mini`, `openai/text-embedding-3-small`. |
| `EVENT_THRESHOLD` / `MIN_COOLDOWN_MINUTES` / `MAX_STALENESS_HOURS` | Recommendation regeneration triggers. |
| `DIGEST_HOUR` / `DIGEST_MINUTE` | When the daily digest runs (UTC). |
| `DIGEST_DEV_INTERVAL_MINUTES` | Optional: fire the digest every N minutes to demo it without waiting. |
| `SMTP_*` | Optional: if unset, digest emails log to the console instead of sending. |
| `LANGCHAIN_TRACING_V2` / `LANGCHAIN_API_KEY` / `LANGCHAIN_PROJECT` | Optional: enable LangSmith tracing. |

---

## Trying the behavior loop
1. Register a user and browse/search several courses in one category (e.g. the Agentic AI ones).
2. Open **For You** — the agent analyzes your activity, retrieves grounded courses, and writes
   a persuasive narrative referencing your interests.
3. Reloading won't re-call the LLM until the trigger thresholds are met (efficiency) — use the
   **Refresh** button to force a new run.
4. To see the digest without waiting for 3pm, set `DIGEST_DEV_INTERVAL_MINUTES=2` (or run the
   job directly): `python -c "from app.scheduler.jobs import daily_digest_job; daily_digest_job()"`.

## HTTP endpoints
| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/` | — | Course catalog |
| GET | `/products?q=` | — | Search catalog (title/description/category) |
| GET | `/products/{id}` | — | Course detail (fires a `product_view`) |
| GET/POST | `/register`, `/login`, `/logout` | — | Auth |
| GET | `/recommendations` | user | Personalized picks (lazily regenerated, gated) |
| POST | `/recommendations/refresh` | user | Force a fresh agent run |
| GET | `/admin/products` | admin | Product list |
| GET/POST | `/admin/products/new`, `/admin/products/{id}/edit`, `/admin/products/{id}/delete` | admin | CRUD (dual-write) |
| POST | `/api/events` | optional | Batched behavioral event ingestion (204) |
| GET | `/health` | — | Liveness + SQL/vector-store status |

## Tests
```bash
pytest -q
```
All tests mock Mesh, so the suite runs **without an API key**. Coverage: dual-write consistency
(incl. a simulated Chroma failure + reconciliation), bulk event ingestion, the trigger/cooldown
logic, the LangGraph agent's routing + grounding (hallucinated ids are dropped), email
validation + password hashing, and the digest activity recap.

## Project layout
```
app/
  main.py            app factory, lifespan (scheduler), /health
  config.py db.py security.py deps.py
  models/            user · product · event · recommendation
  schemas/           auth · product · event
  routers/           auth · pages · admin_products · events · recommendations
  services/          product_service · event_service · vector_store · mesh_client
                     recommendation_service · email_service
  agent/             graph · state · llm · tracing · nodes/{analyze_activity,retrieve,
                     grade_retrieval,refine_query,rerank,generate_copy}
  scheduler/jobs.py  daily_digest_job · reconcile_job
  templates/         base · auth · catalog · admin/ · emails/digest_email
static/js/tracker.js batched/throttled/sendBeacon tracking
scripts/             init_db · seed_products · reconcile_vector_store
tests/               dual-write · events · trigger · agent-graph · auth · digest-recap
```

## Continuous integration / submission
The official checks live at `.github/workflows/smartreco-checks.yml`. For them to run, add two
repository secrets (Settings → Secrets and variables → Actions):
- `MESH_API_KEY` — your Mesh key.
- `SUBMISSION_TOKEN` — from your submission dashboard.

Critical checks: all Python compiles, and `requirements.txt` lists a web framework + LLM client
(both satisfied). `.env` is gitignored and never committed.

## Troubleshooting
- **`402 spend_limit_exceeded` from Mesh** — the account has no balance. Embeddings are a paid
  Mesh model (no free embedding model exists on Mesh), though usage is tiny; top up a little.
- **`bcrypt` / passlib error at startup** — `requirements.txt` pins `bcrypt==4.0.1` because
  passlib 1.7.4's self-test breaks on bcrypt ≥ 4.1. Reinstall from requirements if you see it.
- **Recommendations don't change on reload** — that's the trigger/caching working. Use the
  **Refresh** button, or generate enough new events to cross `EVENT_THRESHOLD` after the cooldown.
- **Digest email doesn't send** — with no `SMTP_*` configured it logs the rendered email to the
  console instead; that's expected. Check the server log.

## Design tradeoffs & limitations
- SQLite + in-process Chroma + in-process APScheduler are chosen for zero-setup runnability; a
  production build would use Postgres, a managed vector DB, and a separate scheduler/worker.
- One recommendation row per user (updated in place) rather than a history table.
- The session is a signed stateless cookie (no server-side revocation).
- `/recommendations` regenerates synchronously when triggered; the `status` field is modeled to
  support an async "regenerating…" UX as a future step.

## Tech
FastAPI · SQLite (SQLAlchemy) · Chroma · Jinja2 + vanilla JS · Mesh API (OpenAI SDK &
langchain-openai) · LangGraph · APScheduler · LangSmith.
