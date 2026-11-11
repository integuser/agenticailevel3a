from unittest.mock import MagicMock, patch

import pytest

from ai_generator import AIGenerator
from tests.conftest import make_response, text_block, tool_use_block

TOOLS = [{"name": "search_course_content"}]


@pytest.fixture
def gen():
    with patch("ai_generator.anthropic.Anthropic") as cls:
        g = AIGenerator("k", "m")
        g.client = cls.return_value
        yield g


def test_tools_passed(gen):
    gen.client.messages.create.return_value = make_response([text_block("hi")])
    assert gen.generate_response("q", tools=TOOLS, tool_manager=MagicMock()) == "hi"
    kw = gen.client.messages.create.call_args.kwargs
    assert kw["tools"] == TOOLS and kw["tool_choice"] == {"type": "auto"}


def test_direct_answer_no_tool(gen):
    gen.client.messages.create.return_value = make_response([text_block("hi")])
    tm = MagicMock()
    gen.generate_response("q", tools=TOOLS, tool_manager=tm)
    tm.execute_tool.assert_not_called()


def test_tool_flow(gen):
    tu = tool_use_block(input={"query": "mcp", "course_name": "X"})
    gen.client.messages.create.side_effect = [
        make_response([tu], "tool_use"), make_response([text_block("final")])]
    tm = MagicMock()
    tm.execute_tool.return_value = "result"
    assert gen.generate_response("q", tools=TOOLS, tool_manager=tm) == "final"
    tm.execute_tool.assert_called_once_with("search_course_content", query="mcp", course_name="X")
    second = gen.client.messages.create.call_args_list[1].kwargs
    assert second["messages"][1]["content"] == [tu]
    assert second["messages"][2]["content"] == [
        {"type": "tool_result", "tool_use_id": "toolu_1", "content": "result"}]


def test_followup_empty_content(gen):
    gen.client.messages.create.side_effect = [
        make_response([tool_use_block()], "tool_use"), make_response([])]
    tm = MagicMock()
    tm.execute_tool.return_value = "r"
    assert isinstance(gen.generate_response("q", tools=TOOLS, tool_manager=tm), str)


def test_followup_second_tool_use(gen):
    gen.client.messages.create.side_effect = [
        make_response([tool_use_block()], "tool_use"),
        make_response([tool_use_block(id="toolu_2")], "tool_use"),
        make_response([tool_use_block(id="toolu_3")], "tool_use")]
    tm = MagicMock()
    tm.execute_tool.return_value = "r"
    assert isinstance(gen.generate_response("q", tools=TOOLS, tool_manager=tm), str)


def test_system_prompt_mentions_tools():
    assert "search_course_content" in AIGenerator.SYSTEM_PROMPT
    assert "get_course_outline" in AIGenerator.SYSTEM_PROMPT


def _tm(*results):
    tm = MagicMock()
    tm.execute_tool.side_effect = list(results) if results else None
    return tm


def test_two_sequential_rounds(gen):
    gen.client.messages.create.side_effect = [
        make_response([tool_use_block(name="get_course_outline", input={"course_name": "X"})], "tool_use"),
        make_response([tool_use_block(id="toolu_2")], "tool_use"),
        make_response([text_block("done")])]
    tm = _tm("outline", "content")
    assert gen.generate_response("q", tools=TOOLS, tool_manager=tm) == "done"
    assert gen.client.messages.create.call_count == 3
    assert [c.args[0] for c in tm.execute_tool.call_args_list] == [
        "get_course_outline", "search_course_content"]


def test_context_preserved(gen):
    t1, t2 = tool_use_block(), tool_use_block(id="toolu_2")
    gen.client.messages.create.side_effect = [
        make_response([t1], "tool_use"), make_response([t2], "tool_use"),
        make_response([text_block("done")])]
    gen.generate_response("q", tools=TOOLS, tool_manager=_tm("a", "b"))
    msgs = gen.client.messages.create.call_args_list[2].kwargs["messages"]
    assert [m["role"] for m in msgs] == ["user", "assistant", "user", "assistant", "user"]
    assert msgs[2]["content"][0]["tool_use_id"] == "toolu_1"
    assert msgs[4]["content"][0]["tool_use_id"] == "toolu_2"


def test_round_cap(gen):
    gen.client.messages.create.side_effect = [
        make_response([tool_use_block(id=f"toolu_{i}")], "tool_use") for i in range(3)]
    tm = _tm("a", "b", "c")
    assert isinstance(gen.generate_response("q", tools=TOOLS, tool_manager=tm), str)
    assert tm.execute_tool.call_count == 2
    calls = gen.client.messages.create.call_args_list
    assert len(calls) == 3
    assert "tools" in calls[1].kwargs and "tools" not in calls[2].kwargs


def test_tool_exception(gen):
    gen.client.messages.create.side_effect = [
        make_response([tool_use_block()], "tool_use"), make_response([text_block("sorry")])]
    tm = MagicMock()
    tm.execute_tool.side_effect = RuntimeError("boom")
    assert gen.generate_response("q", tools=TOOLS, tool_manager=tm) == "sorry"
    calls = gen.client.messages.create.call_args_list
    assert len(calls) == 2
    res = calls[1].kwargs["messages"][2]["content"][0]
    assert res["is_error"] and "boom" in res["content"]
    assert "tools" not in calls[1].kwargs


def test_tool_error_string_allows_round_two(gen):
    gen.client.messages.create.side_effect = [
        make_response([tool_use_block()], "tool_use"),
        make_response([tool_use_block(id="toolu_2")], "tool_use"),
        make_response([text_block("ok")])]
    tm = _tm("Search error: x", "good")
    assert gen.generate_response("q", tools=TOOLS, tool_manager=tm) == "ok"
    assert tm.execute_tool.call_count == 2


def test_multiple_tool_use_blocks(gen):
    a, b = tool_use_block(id="toolu_a"), tool_use_block(id="toolu_b")
    gen.client.messages.create.side_effect = [
        make_response([a, b], "tool_use"), make_response([text_block("ok")])]
    tm = _tm("r1", "r2")
    gen.generate_response("q", tools=TOOLS, tool_manager=tm)
    assert tm.execute_tool.call_count == 2
    msgs = gen.client.messages.create.call_args_list[1].kwargs["messages"]
    assert [r["tool_use_id"] for r in msgs[2]["content"]] == ["toolu_a", "toolu_b"]


def test_tool_use_without_tool_manager(gen):
    gen.client.messages.create.return_value = make_response([tool_use_block()], "tool_use")
    assert isinstance(gen.generate_response("q", tools=TOOLS, tool_manager=None), str)


def test_system_prompt_sequential_calls():
    assert "One tool call per query maximum" not in AIGenerator.SYSTEM_PROMPT
    assert "2 sequential" in AIGenerator.SYSTEM_PROMPT
