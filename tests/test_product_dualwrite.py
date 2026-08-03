"""Dual-write consistency: SQL and Chroma stay in sync across create/update/delete,
the failure path flips vector_sync_status, and reconciliation repairs drift."""


def test_create_writes_both_stores(env):
    db = env["db_module"].SessionLocal()
    ps, vs = env["product_service"], env["vector_store"]
    try:
        p = ps.create_product(db, {"title": "Test Course", "category": "Agentic AI", "price": 10.0})
        assert p.id is not None
        assert p.vector_sync_status == "synced"
        assert str(p.id) in vs.get_ids()
        assert vs.count() == 1
    finally:
        db.close()


def test_update_reembeds(env):
    db = env["db_module"].SessionLocal()
    ps, vs = env["product_service"], env["vector_store"]
    try:
        p = ps.create_product(db, {"title": "Old", "category": "Web", "price": 5.0})
        ps.update_product(db, p.id, {"title": "New Title", "category": "Web", "price": 5.0})
        # Same id, still exactly one vector entry (upsert, not duplicate).
        assert vs.count() == 1
        got = vs.get_collection().get(ids=[str(p.id)], include=["metadatas"])
        assert got["metadatas"][0]["title"] == "New Title"
    finally:
        db.close()


def test_soft_delete_removes_from_vector_store(env):
    db = env["db_module"].SessionLocal()
    ps, vs = env["product_service"], env["vector_store"]
    Product = env["product_model"]
    try:
        p = ps.create_product(db, {"title": "Doomed", "category": "Web", "price": 5.0})
        pid = p.id
        assert ps.delete_product(db, pid) is True
        # SQL row still exists (soft delete) but is inactive; vector entry gone.
        row = db.get(Product, pid)
        assert row.is_active is False
        assert str(pid) not in vs.get_ids()
        assert vs.count() == 0
    finally:
        db.close()


def test_failed_vector_write_flags_and_reconciles(env, monkeypatch):
    db = env["db_module"].SessionLocal()
    ps, vs = env["product_service"], env["vector_store"]
    Product = env["product_model"]
    try:
        # Force the Chroma upsert to blow up so the SQL write succeeds but the vector write fails.
        def boom(*a, **k):
            raise RuntimeError("chroma down")

        original_upsert = vs.upsert_product
        monkeypatch.setattr(vs, "upsert_product", boom)
        p = ps.create_product(db, {"title": "Flaky", "category": "Web", "price": 5.0})
        assert p.vector_sync_status == "failed"  # SQL committed, vector flagged for repair
        assert vs.count() == 0

        # Restore ONLY the injected failure (keep the fake-embedding patch intact), then reconcile.
        monkeypatch.setattr(vs, "upsert_product", original_upsert)
        from scripts.reconcile_vector_store import reconcile

        summary = reconcile()
        assert summary["fixed"] == 1
        db.refresh(p)
        assert p.vector_sync_status == "synced"
        assert str(p.id) in vs.get_ids()
    finally:
        db.close()
