import os
from unittest.mock import MagicMock, patch

import pytest

from config import config
from tests.conftest import make_response, text_block, tool_use_block


def build():
    from rag_system import RAGSystem
    with patch("rag_system.AIGenerator") as gen_cls, \
         patch("rag_system.VectorStore"):
        rag = RAGSystem(config)
    return rag, gen_cls.return_value


def test_query_passes_tools_and_manager():
    rag, gen = build()
    gen.generate_response.return_value = "ans"
    resp, sources = rag.query("what is MCP")
    kw = gen.generate_response.call_args.kwargs
    assert {t["name"] for t in kw["tools"]} == {"search_course_content", "get_course_outline"}
    assert kw["tool_manager"] is rag.tool_manager
    assert resp == "ans" and sources == []


def test_sources_returned_then_reset():
    rag, gen = build()

    def fake(**kw):
        rag.search_tool.last_sources = [{"text": "C - Lesson 1", "url": None}]
        return "ans"
    gen.generate_response.side_effect = fake
    _, sources = rag.query("q")
    assert sources == [{"text": "C - Lesson 1", "url": None}]
    assert rag.search_tool.last_sources == []


def test_session_history_updated():
    rag, gen = build()
    gen.generate_response.return_value = "ans"
    sid = rag.session_manager.create_session()
    rag.query("q1", sid)
    assert "q1" in rag.session_manager.get_conversation_history(sid)


def test_generator_exception_propagates():
    rag, gen = build()
    gen.generate_response.side_effect = RuntimeError("boom")
    with pytest.raises(RuntimeError):
        rag.query("q")


def _real_rag(real_store):
    from rag_system import RAGSystem
    with patch("rag_system.VectorStore", return_value=real_store):
        return RAGSystem(config)


def test_end_to_end_fake_anthropic(real_store):
    rag = _real_rag(real_store)
    client = MagicMock()
    client.messages.create.side_effect = [
        make_response([tool_use_block(input={"query": "what is MCP"})], "tool_use"),
        make_response([text_block("MCP is ...")])]
    rag.ai_generator.client = client
    resp, sources = rag.query("what is MCP")
    assert resp == "MCP is ..."
    tool_result = client.messages.create.call_args_list[1].kwargs["messages"][2]["content"][0]["content"]
    assert not tool_result.startswith("Search error")
    assert sources


@pytest.mark.skipif(not os.getenv("ANTHROPIC_API_KEY"), reason="no API key")
def test_live_smoke(real_store):
    resp, _ = _real_rag(real_store).query("What is MCP?")
    assert resp
