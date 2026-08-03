"""Test harness: a session-wide temp SQLite DB + temp Chroma dir, and a fake (offline)
embedding function so the dual-write / retrieval paths can be exercised without spending
Mesh balance.

The env vars are set at import time — before any `app.*` module is imported — so
app.config binds to the temp locations on first import. The fake ONLY replaces the
network call inside mesh_client.embed_texts; the full production code path
(product_service -> vector_store -> mesh_client.embed_text) is otherwise exercised for real.
"""
import hashlib
import os
import tempfile
from pathlib import Path

_TMP = tempfile.mkdtemp(prefix="smartreco_test_")
os.environ["DATABASE_URL"] = f"sqlite:///{Path(_TMP) / 'test.db'}"
os.environ["CHROMA_DIR"] = str(Path(_TMP) / "chroma")

import pytest  # noqa: E402

import app.db as db_module  # noqa: E402

# Import every model so the full schema (and all FKs) is registered on Base.metadata
# before create_all runs.
import app.models.event  # noqa: E402, F401
import app.models.product  # noqa: E402, F401
import app.models.recommendation  # noqa: E402, F401
import app.models.user  # noqa: E402, F401
import app.services.mesh_client as mesh_client  # noqa: E402
import app.services.product_service as product_service  # noqa: E402
import app.services.vector_store as vector_store  # noqa: E402
from app.models.product import Product  # noqa: E402


def _fake_embed_texts(texts, purpose=None, **_kwargs):
    # Deterministic 32-dim pseudo-embedding from the text hash — offline, order-preserving.
    out = []
    for t in texts:
        h = hashlib.sha256(t.encode()).digest()
        out.append([b / 255.0 for b in h[:32]])
    return out


@pytest.fixture()
def env(monkeypatch):
    # Offline embeddings.
    monkeypatch.setattr(mesh_client, "embed_texts", _fake_embed_texts)

    # Fresh SQL schema per test.
    db_module.Base.metadata.drop_all(bind=db_module.engine)
    db_module.Base.metadata.create_all(bind=db_module.engine)

    # Fresh Chroma collection per test.
    col = vector_store.get_collection()
    existing = col.get(include=[]).get("ids", [])
    if existing:
        col.delete(ids=existing)

    yield {
        "db_module": db_module,
        "product_service": product_service,
        "vector_store": vector_store,
        "mesh_client": mesh_client,
        "product_model": Product,
    }
