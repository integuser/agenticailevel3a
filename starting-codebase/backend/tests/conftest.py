import os
import sys
from types import SimpleNamespace

import pytest

BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

CHROMA_PATH = os.path.join(BACKEND, "chroma_db")


def text_block(text):
    return SimpleNamespace(type="text", text=text)


def tool_use_block(name="search_course_content", input=None, id="toolu_1"):
    return SimpleNamespace(
        type="tool_use", name=name, input=input or {"query": "mcp"}, id=id
    )


def make_response(content, stop_reason="end_turn"):
    return SimpleNamespace(content=content, stop_reason=stop_reason)


@pytest.fixture
def real_store():
    """Real VectorStore on the existing chroma_db; skipped if empty/missing."""
    if not os.path.isdir(CHROMA_PATH):
        pytest.skip("chroma_db missing")
    from vector_store import VectorStore

    store = VectorStore(CHROMA_PATH, "all-MiniLM-L6-v2", 5)
    if store.course_content.count() == 0:
        pytest.skip("chroma_db empty")
    return store


# ---- API test infrastructure -------------------------------------------------
# backend/app.py builds a real RAGSystem and mounts ../frontend at import time,
# so API tests use a standalone app that mirrors its endpoints around a mock RAG.

from typing import List, Optional  # noqa: E402

from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from pydantic import BaseModel  # noqa: E402


class QueryRequest(BaseModel):
    query: str
    session_id: Optional[str] = None


class Source(BaseModel):
    text: str
    url: Optional[str] = None


class QueryResponse(BaseModel):
    answer: str
    sources: List[Source]
    session_id: str


class CourseStats(BaseModel):
    total_courses: int
    course_titles: List[str]


def create_test_app(rag_system, static_dir) -> FastAPI:
    """Mirror of app.py's endpoints, bound to the given rag_system and static dir."""
    app = FastAPI()

    @app.post("/api/query", response_model=QueryResponse)
    async def query_documents(request: QueryRequest):
        try:
            session_id = request.session_id or rag_system.session_manager.create_session()
            answer, sources = rag_system.query(request.query, session_id)
            return QueryResponse(answer=answer, sources=sources, session_id=session_id)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.delete("/api/session/{session_id}")
    async def delete_session(session_id: str):
        rag_system.session_manager.delete_session(session_id)
        return {"status": "ok"}

    @app.get("/api/courses", response_model=CourseStats)
    async def get_course_stats():
        try:
            a = rag_system.get_course_analytics()
            return CourseStats(total_courses=a["total_courses"], course_titles=a["course_titles"])
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")
    return app


@pytest.fixture
def sample_sources():
    return [
        {"text": "MCP Course - Lesson 1", "url": "http://example.com/l1"},
        {"text": "MCP Course - Lesson 2", "url": None},
    ]


@pytest.fixture
def mock_rag(sample_sources):
    from unittest.mock import MagicMock
    rag = MagicMock()
    rag.session_manager.create_session.return_value = "session_1"
    rag.query.return_value = ("test answer", sample_sources)
    rag.get_course_analytics.return_value = {
        "total_courses": 2, "course_titles": ["MCP Course", "Chroma Course"]}
    return rag


@pytest.fixture
def static_dir(tmp_path):
    (tmp_path / "index.html").write_text("<html><body>RAG Chatbot</body></html>")
    return tmp_path


@pytest.fixture
def client(mock_rag, static_dir):
    return TestClient(create_test_app(mock_rag, static_dir))
