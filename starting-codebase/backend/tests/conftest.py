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
