from unittest.mock import MagicMock

from search_tools import CourseSearchTool
from vector_store import SearchResults


def make_tool(results):
    store = MagicMock()
    store.search.return_value = results
    store.get_lesson_link.return_value = "http://link"
    return CourseSearchTool(store), store


def res(docs, metas):
    return SearchResults(documents=docs, metadata=metas, distances=[0.1] * len(docs))


def test_format_and_sources():
    tool, _ = make_tool(res(["a", "b"], [
        {"course_title": "C", "lesson_number": 1},
        {"course_title": "C", "lesson_number": 1}]))
    out = tool.execute("q")
    assert "[C - Lesson 1]\na" in out and "[C - Lesson 1]\nb" in out
    assert tool.last_sources == [{"text": "C - Lesson 1", "url": "http://link"}]


def test_passthrough_args():
    tool, store = make_tool(res(["a"], [{"course_title": "C", "lesson_number": 2}]))
    tool.execute("q", course_name="MCP", lesson_number=2)
    store.search.assert_called_once_with(query="q", course_name="MCP", lesson_number=2)


def test_error_returned():
    tool, _ = make_tool(SearchResults.empty("Search error: boom"))
    assert tool.execute("q") == "Search error: boom"


def test_empty_message():
    tool, _ = make_tool(res([], []))
    assert tool.execute("q", course_name="X", lesson_number=3) == \
        "No relevant content found in course 'X' in lesson 3."


def test_lesson_zero_in_empty_message():
    tool, _ = make_tool(res([], []))
    # Expected to fail today: `if lesson_number:` ignores 0
    assert "lesson 0" in tool.execute("q", lesson_number=0)


# Integration (real chroma_db)
def test_real_search_no_error(real_store):
    r = real_store.search("what is MCP")
    assert r.error is None, r.error


def test_real_execute(real_store):
    out = CourseSearchTool(real_store).execute("what is MCP")
    assert not out.startswith("Search error")


def test_real_course_name_resolves(real_store):
    out = CourseSearchTool(real_store).execute("what is MCP", course_name="MCP")
    assert not out.startswith(("Search error", "No course found"))
