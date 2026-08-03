"""Seed the catalog with sample courses via the real dual-write path (SQL + Chroma).

Idempotent: skips products whose title already exists. Requires a funded Mesh account
(embeddings are computed through Mesh during the dual-write).

Usage: python -m scripts.seed_products
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from app.db import SessionLocal, create_all
from app.models.product import Product
from app.services import product_service

# SmartReco catalog — AI/ML learning marketplace.
SAMPLE_PRODUCTS = [
    # Generative AI
    {"title": "Building Production RAG Systems", "category": "Generative AI", "price": 189.0, "level": "intermediate", "rating": 4.8, "students": 3200,
     "description": "Ship retrieval that actually holds up under real traffic. Chunking, hybrid search, reranking, evaluation, and guardrails for grounded, hallucination-resistant answers."},
    {"title": "Prompt Engineering for Real Products", "category": "Generative AI", "price": 129.0, "level": "beginner", "rating": 4.6, "students": 5100,
     "description": "Structured outputs, few-shot patterns, and evaluation loops that make LLM features reliable instead of a demo that breaks in production."},
    {"title": "Fine-Tuning and Adapters in Practice", "category": "Generative AI", "price": 209.0, "level": "advanced", "rating": 4.7, "students": 1400,
     "description": "LoRA, QLoRA, and instruction tuning end to end: data curation, training runs, evaluation, and deciding when fine-tuning beats prompting or RAG."},

    # Agentic AI
    {"title": "Agentic Workflows with LangGraph", "category": "Agentic AI", "price": 219.0, "level": "advanced", "rating": 4.9, "students": 2187,
     "description": "Model agents as state machines, add tool use, memory and retries, and instrument every step so you can debug what your agent actually did."},
    {"title": "Building Tool-Using AI Agents", "category": "Agentic AI", "price": 179.0, "level": "intermediate", "rating": 4.7, "students": 2600,
     "description": "Function calling, planning loops, self-grading, and refinement. Build agents that decide when to retrieve, act, and stop — grounded in real data."},
    {"title": "Multi-Agent Systems and Orchestration", "category": "Agentic AI", "price": 199.0, "level": "advanced", "rating": 4.6, "students": 980,
     "description": "Coordinate multiple specialized agents: routing, shared memory, handoffs, and evaluation of collaborative workflows without the chaos."},

    # MLOps
    {"title": "MLOps for Real Teams", "category": "MLOps", "price": 179.0, "level": "intermediate", "rating": 4.7, "students": 1800,
     "description": "The pipeline, review and rollout habits mature ML orgs share. Experiment tracking, model registries, CI/CD, and monitoring that catches drift."},
    {"title": "Model Serving and Inference at Scale", "category": "MLOps", "price": 189.0, "level": "advanced", "rating": 4.5, "students": 1100,
     "description": "Latency, batching, GPU utilization, and cost. Serve models that stay fast and cheap under load with autoscaling and observability."},
    {"title": "ML Monitoring and Drift Detection", "category": "MLOps", "price": 149.0, "level": "intermediate", "rating": 4.6, "students": 1350,
     "description": "Detect data and concept drift, wire up alerting, and build the feedback loops that keep production models honest over time."},

    # Data Engineering
    {"title": "Data Engineering for AI Pipelines", "category": "Data Engineering", "price": 169.0, "level": "intermediate", "rating": 4.6, "students": 2400,
     "description": "Batch and streaming pipelines, orchestration, and warehouse modeling that feed reliable data into training and inference."},
    {"title": "Vector Databases in Depth", "category": "Data Engineering", "price": 139.0, "level": "intermediate", "rating": 4.7, "students": 2900,
     "description": "How embeddings, ANN indexes (HNSW), and metadata filtering actually work. Hands-on with Chroma, Qdrant, and FAISS for semantic search."},
    {"title": "Streaming Data with Kafka and Flink", "category": "Data Engineering", "price": 159.0, "level": "advanced", "rating": 4.4, "students": 860,
     "description": "Real-time event pipelines: exactly-once semantics, windowing, and stateful processing for analytics and ML features."},

    # Cloud & DevOps
    {"title": "Docker and Kubernetes for ML", "category": "Cloud & DevOps", "price": 149.0, "level": "intermediate", "rating": 4.6, "students": 3050,
     "description": "Containerize models and services, orchestrate them on Kubernetes, and ship with health checks, scaling, and safe rollouts."},
    {"title": "CI/CD Pipelines with GitHub Actions", "category": "Cloud & DevOps", "price": 99.0, "level": "beginner", "rating": 4.5, "students": 4200,
     "description": "Automate testing and deployment with workflows, secrets, and matrix builds — the same setup that gates real production releases."},
    {"title": "Observability: Logs, Metrics, Tracing", "category": "Cloud & DevOps", "price": 119.0, "level": "intermediate", "rating": 4.6, "students": 1700,
     "description": "Instrument systems for insight. Structured logging, metrics, and distributed tracing so you can debug what actually happened."},

    # Python for AI
    {"title": "Python for AI Engineers", "category": "Python for AI", "price": 89.0, "level": "beginner", "rating": 4.7, "students": 6400,
     "description": "The Python that AI work actually needs: async, typing, packaging, testing, and the data stack — written the way production teams write it."},
    {"title": "Async Python and Concurrency", "category": "Python for AI", "price": 109.0, "level": "intermediate", "rating": 4.5, "students": 2100,
     "description": "asyncio, tasks, and non-blocking I/O for fast APIs and data pipelines — with the pitfalls and patterns that trip people up."},
    {"title": "Testing and Packaging Python Projects", "category": "Python for AI", "price": 79.0, "level": "beginner", "rating": 4.4, "students": 2750,
     "description": "pytest, fixtures, mocking, and clean packaging so your AI code is reproducible, installable, and safe to change."},
]


def main() -> None:
    create_all()
    db = SessionLocal()
    created, skipped = 0, 0
    try:
        for data in SAMPLE_PRODUCTS:
            exists = db.scalar(select(Product).where(Product.title == data["title"]))
            if exists:
                skipped += 1
                continue
            product_service.create_product(db, data)
            created += 1
            print(f"  + {data['title']}")
        print(f"\nSeed complete: {created} created, {skipped} skipped (already existed).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
