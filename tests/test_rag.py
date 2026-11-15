"""
tests/test_rag.py
=================
Unit tests for the Retrieval-Augmented Generation (RAG) engine.
"""

import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest
from src.rag.engine import RAGEngine, DEFAULT_KNOWLEDGE_BASE, tokenize


def test_rag_tokenize():
    tokens = tokenize("How does high slope angle cause landslides in Wayanad?")
    assert "slope" in tokens
    assert "angle" in tokens
    assert "landslid" in tokens or "landslides" in tokens
    assert "wayanad" in tokens
    assert "the" not in tokens
    assert "how" not in tokens


def test_rag_engine_initialization():
    rag = RAGEngine()
    assert len(rag.corpus) >= 12
    assert rag.N >= 12
    assert len(rag.idf) > 20


def test_rag_retrieve_slope_query():
    rag = RAGEngine()
    results = rag.retrieve("What is the effect of slope angle and elevation on landslides?", top_k=3)
    assert len(results) == 3
    top_doc = results[0]["doc"]
    assert "Slope" in top_doc["title"] or "Topographic" in top_doc["title"]
    assert results[0]["score"] > 0.05


def test_rag_retrieve_statespace_query():
    rag = RAGEngine()
    results = rag.retrieve("Why use state-space DLM Kalman filter for soil moisture drainage?", top_k=3)
    titles = [r["doc"]["title"] for r in results]
    assert any("State-Space" in t or "Soil Saturation" in t for t in titles)


def test_rag_retrieve_wayanad_spatial_cv():
    rag = RAGEngine()
    results = rag.retrieve("Wayanad spatial cross-validation fold A1 100% recall", top_k=3)
    titles = [r["doc"]["title"] for r in results]
    assert any("Wayanad" in t or "Spatial" in t for t in titles)


def test_rag_add_custom_document():
    rag = RAGEngine()
    initial_count = len(rag.corpus)
    doc_id = rag.add_document(
        title="Nilgiris Ghat Road Geotechnical Survey 2026",
        category="Field Survey",
        content="Ghat road sector km 14 to 22 exhibits active tension cracks along colluvium toe cuttings."
    )
    assert len(rag.corpus) == initial_count + 1
    assert doc_id.startswith("custom-")

    # Verify retrieval of newly indexed document
    results = rag.retrieve("Nilgiris ghat road tension cracks", top_k=2)
    assert results[0]["doc"]["title"] == "Nilgiris Ghat Road Geotechnical Survey 2026"


def test_rag_answer_query():
    rag = RAGEngine()
    res = rag.answer_query("Explain NDMA Standard Operating Procedures for warning tier", top_k=2)
    assert "query" in res
    assert "answer" in res
    assert "retrieved_sources" in res
    assert len(res["retrieved_sources"]) == 2
    assert "NDMA" in res["answer"] or "Procedures" in res["answer"]
