import pytest


def test_query_without_session_creates_one(client, mock_rag, sample_sources):
    r = client.post("/api/query", json={"query": "what is MCP"})
    assert r.status_code == 200
    assert r.json() == {"answer": "test answer", "sources": sample_sources, "session_id": "session_1"}
    mock_rag.session_manager.create_session.assert_called_once()
    mock_rag.query.assert_called_once_with("what is MCP", "session_1")


def test_query_with_existing_session(client, mock_rag):
    r = client.post("/api/query", json={"query": "q", "session_id": "abc"})
    assert r.json()["session_id"] == "abc"
    mock_rag.session_manager.create_session.assert_not_called()
    mock_rag.query.assert_called_once_with("q", "abc")


def test_query_empty_sources(client, mock_rag):
    mock_rag.query.return_value = ("hi", [])
    assert client.post("/api/query", json={"query": "q"}).json()["sources"] == []


@pytest.mark.parametrize("body", [{}, {"session_id": "x"}, {"query": 123}, {"query": None}])
def test_query_invalid_body_422(client, body):
    assert client.post("/api/query", json=body).status_code == 422


def test_query_malformed_json_422(client):
    r = client.post("/api/query", content="not json", headers={"Content-Type": "application/json"})
    assert r.status_code == 422


def test_query_wrong_method(client):
    # The "/" static mount shadows Starlette's 405, so GET falls through to a 404
    assert client.get("/api/query").status_code in (404, 405)


def test_query_rag_error_500(client, mock_rag):
    mock_rag.query.side_effect = RuntimeError("boom")
    r = client.post("/api/query", json={"query": "q"})
    assert r.status_code == 500 and r.json()["detail"] == "boom"


def test_courses(client):
    r = client.get("/api/courses")
    assert r.status_code == 200
    assert r.json() == {"total_courses": 2, "course_titles": ["MCP Course", "Chroma Course"]}


def test_courses_empty(client, mock_rag):
    mock_rag.get_course_analytics.return_value = {"total_courses": 0, "course_titles": []}
    assert client.get("/api/courses").json() == {"total_courses": 0, "course_titles": []}


def test_courses_error_500(client, mock_rag):
    mock_rag.get_course_analytics.side_effect = RuntimeError("db down")
    r = client.get("/api/courses")
    assert r.status_code == 500 and r.json()["detail"] == "db down"


def test_delete_session(client, mock_rag):
    r = client.delete("/api/session/abc")
    assert r.status_code == 200 and r.json() == {"status": "ok"}
    mock_rag.session_manager.delete_session.assert_called_once_with("abc")


def test_root_serves_index(client):
    r = client.get("/")
    assert r.status_code == 200 and "RAG Chatbot" in r.text


def test_unknown_path_404(client):
    assert client.get("/nope.html").status_code == 404
