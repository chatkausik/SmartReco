# SmartReco — Deploy, Demo Video & LangSmith Guide

Everything you need to produce the two "reviewed for finalists" assets (a **live URL** and a
**demo video**) plus a **live LangSmith trace** screenshot. The app code is already deploy-ready
(`Procfile`, `render.yaml`, and an `AUTO_SEED_ON_STARTUP` boot guard are in the repo).

---

## 1. Deploy a public URL (Render — free tier)

Render reads the `render.yaml` Blueprint in this repo.

1. Push this repo to GitHub (see the checklist at the bottom).
2. Go to **render.com → New → Blueprint**, connect the repo. Render detects `render.yaml`.
3. When prompted, fill the secrets it can't infer:
   - `MESH_API_KEY` = your funded `rsk_...` key (**required** — seeding + recs embed through Mesh).
   - `BOOTSTRAP_ADMIN_EMAIL` / `BOOTSTRAP_ADMIN_PASSWORD` = your admin login.
   - `SECRET_KEY` is auto-generated; `AUTO_SEED_ON_STARTUP=true` is preset.
4. Click **Apply**. First boot runs `pip install`, then (empty catalog) seeds the 18 courses via
   the real Mesh dual-write. Watch the logs for `AUTO_SEED_ON_STARTUP … seeding products`.
5. Hit `https://<your-app>.onrender.com/health` — expect `"status":"ok"` and
   `"products_indexed": 18`. You're live.

**Data persistence:** the free plan's disk is **ephemeral** — `smartreco.db` + `chroma_data`
reset on every redeploy/restart, and `AUTO_SEED_ON_STARTUP` re-seeds them each boot (fine for a
demo). For durable data, attach a **Render Persistent Disk** mounted at `/data` and set
`DATABASE_URL=sqlite:////data/smartreco.db` and `CHROMA_DIR=/data/chroma_data`.

> Any Procfile-based host works too (Railway, Fly, Heroku-style). The `Procfile` binds
> `0.0.0.0:$PORT`; just set the same env vars.

---

## 2. Record the demo video (~2.5 min, tells the "not faked" story)

Record at 1280×720+. Suggested shot list — each beat maps to a judged requirement:

| # | Beat | Say / show | Proves |
|---|------|-----------|--------|
| 1 | **Register + browse** (~25s) | Sign up, open 3–4 **Agentic AI** courses, run a search. Point at the **Your Signal** panel filling with live chips. | Rich behavioral tracking, non-blocking |
| 2 | **Admin dual-write** (~20s) | As admin, add a product at `/admin/products/new`; note it appears in the catalog. Mention it wrote to SQL **and** Chroma. | Genuine dual-write, kept in sync |
| 3 | **For You narrative** (~25s) | Open **For You**. Read the persuasive, personalized narrative + the specific recommended courses. | Persuasive, catalog-grounded recs |
| 4 | **Explainability trace** (~30s) | Expand **"How the agent chose these."** Walk the pipeline: interest summary → retrieval query + metadata filters → **grade** + refine loop → rerank scores. | Real agentic RAG reasoning (the anti-faking money shot) |
| 5 | **MeshAPI Console** (~25s) | Open the **MeshAPI Console** (top nav). Show the real chat + embedding calls that just ran, with model, tokens, latency, and node. | Every LLM/embedding call goes through Mesh — nothing stubbed |
| 6 | **LangSmith trace** (~15s) | Cut to the LangSmith run (section 3) — the full node graph traced end to end. | Observability bonus |
| 7 | **Efficiency + digest** (~15s) | Reload For You — note it does **not** re-call the LLM (cache/trigger). Show a console-logged digest email. | Production thinking + scheduled delivery bonus |

Tip: set `DIGEST_DEV_INTERVAL_MINUTES=2` before recording so the digest fires on camera, and
`EVENT_THRESHOLD=3` / `MIN_COOLDOWN_MINUTES=0` so recommendations regenerate quickly for beat 7.

---

## 3. Capture a live LangSmith trace

Tracing is already wired (`app/agent/tracing.py`, `app/agent/llm.py`); it's just off by default.

1. Get a key at **smith.langchain.com → Settings → API Keys**.
2. In `.env` (local) or your host's env vars, set:
   ```
   LANGCHAIN_TRACING_V2=true
   LANGCHAIN_API_KEY=lsv2_...
   LANGCHAIN_PROJECT=smartreco
   ```
3. Restart the app, log in, and open **For You** (or hit **Refresh**) to force one agent run.
4. In LangSmith → project **smartreco**, open the newest `reco-user-<id>` run. You'll see the
   full node graph: `analyze_activity → retrieve → grade_retrieval → (refine_query) → rerank →
   generate_copy`, each LLM call with prompts, tokens, and latency.
5. Screenshot it for the README and use it in demo beat 6.

---

## Pre-submission checklist
- [ ] All code committed **and pushed** to the public repo (the repo *is* the submission).
- [ ] Repo secrets set: **`MESH_API_KEY`** + **`SUBMISSION_TOKEN`** (Settings → Secrets → Actions).
- [ ] CI green in the **Actions** tab (compiles + deps present).
- [ ] `.env` is **not** committed (it's gitignored).
- [ ] Live URL + video link pasted into the top of `README.md`.
