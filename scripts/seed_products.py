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

SAMPLE_PRODUCTS = [
    # Agentic AI / LLM engineering
    {"title": "Building Agentic AI Systems with LangGraph", "category": "Agentic AI", "price": 129.0, "level": "advanced",
     "description": "Design multi-step reasoning agents with LangGraph: nodes, conditional edges, retrieval loops, self-grading, and refinement. Build a production RAG agent end to end."},
    {"title": "RAG in Production: Retrieval, Reranking, and Evaluation", "category": "Agentic AI", "price": 99.0, "level": "intermediate",
     "description": "Move beyond naive top-k. Metadata filtering, cross-encoder reranking, chunking strategies, and how to evaluate retrieval quality with real metrics."},
    {"title": "LLM App Engineering with the OpenAI SDK", "category": "Agentic AI", "price": 89.0, "level": "intermediate",
     "description": "Structured outputs, tool calling, streaming, caching, and cost control for LLM-powered applications using the OpenAI-compatible API surface."},
    {"title": "Vector Databases Deep Dive", "category": "Agentic AI", "price": 79.0, "level": "intermediate",
     "description": "How embeddings, ANN indexes (HNSW), and metadata filtering actually work. Hands-on with Chroma, Qdrant, and FAISS for semantic search."},
    {"title": "Prompt Engineering for Reliable Agents", "category": "Agentic AI", "price": 59.0, "level": "beginner",
     "description": "Practical prompting patterns for grounded, persuasive, and safe LLM output. Few-shot, structured extraction, and guardrails against hallucination."},

    # Web / backend
    {"title": "FastAPI from Zero to Production", "category": "Web Development", "price": 94.0, "level": "intermediate",
     "description": "Build async Python APIs with FastAPI: dependency injection, auth, background tasks, SQLAlchemy, testing, and deployment."},
    {"title": "Full-Stack Web Development Bootcamp", "category": "Web Development", "price": 149.0, "level": "beginner",
     "description": "HTML, CSS, JavaScript, and a Python backend. Build and deploy real web applications from scratch with server-rendered templates."},
    {"title": "Scalable Backend Systems Design", "category": "Web Development", "price": 119.0, "level": "advanced",
     "description": "Caching, queues, batching, rate limiting, and non-blocking I/O. Architect backends that stay fast under load."},
    {"title": "JavaScript for Modern Frontends", "category": "Web Development", "price": 69.0, "level": "beginner",
     "description": "The JavaScript you need for interactive UIs: events, fetch, the DOM, debouncing, throttling, and the Beacon API for non-blocking telemetry."},

    # Data / ML
    {"title": "Machine Learning Foundations", "category": "Data Science", "price": 109.0, "level": "beginner",
     "description": "Supervised and unsupervised learning, model evaluation, and the math intuition behind it. Hands-on with scikit-learn."},
    {"title": "Deep Learning with PyTorch", "category": "Data Science", "price": 139.0, "level": "advanced",
     "description": "Neural networks, backpropagation, CNNs, transformers, and training at scale using PyTorch."},
    {"title": "Data Engineering Pipelines", "category": "Data Science", "price": 124.0, "level": "intermediate",
     "description": "Batch and streaming pipelines, orchestration, and warehouse modeling. Move data reliably from source to insight."},
    {"title": "Practical SQL for Analytics", "category": "Data Science", "price": 49.0, "level": "beginner",
     "description": "Window functions, joins, indexing, and query optimization for analysts who need answers from real databases."},

    # Cloud / DevOps
    {"title": "Docker and Kubernetes in Practice", "category": "DevOps", "price": 114.0, "level": "intermediate",
     "description": "Containerize applications, orchestrate them with Kubernetes, and ship with confidence. Health checks, scaling, and rollouts."},
    {"title": "CI/CD with GitHub Actions", "category": "DevOps", "price": 64.0, "level": "beginner",
     "description": "Automate testing and deployment with GitHub Actions workflows, secrets, and matrix builds."},
    {"title": "Observability: Logs, Metrics, and Tracing", "category": "DevOps", "price": 84.0, "level": "intermediate",
     "description": "Instrument systems for insight. Structured logging, metrics, and distributed tracing so you can debug what actually happened."},

    # Product / design
    {"title": "Product Analytics and Behavioral Tracking", "category": "Product", "price": 74.0, "level": "intermediate",
     "description": "Design event schemas, track user behavior without slowing the UX, and turn activity data into product decisions."},
    {"title": "UX Design Fundamentals", "category": "Design", "price": 59.0, "level": "beginner",
     "description": "User research, wireframing, and interaction design principles for building interfaces people love."},

    # Security
    {"title": "Web Application Security Essentials", "category": "Security", "price": 99.0, "level": "intermediate",
     "description": "Auth, sessions, password hashing, and the OWASP Top 10. Secure your web apps against common attacks."},
    {"title": "Applied Cryptography Basics", "category": "Security", "price": 89.0, "level": "advanced",
     "description": "Hashing, symmetric and asymmetric encryption, and signing. Understand the primitives behind secure systems."},
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
