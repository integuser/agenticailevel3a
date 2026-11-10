# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository layout

The git root holds the real project in `starting-codebase/` (a course-materials RAG chatbot) plus untracked course zips that are reference material only. All commands below run from `starting-codebase/`. `starting-codebase/main.py` is a stub and is not part of the app. `starting-codebase/starting-ragchatbot-codebase-main/` is an empty leftover folder.

## Commands

Python 3.13+ and `uv` are required. On Windows, use Git Bash for `run.sh`.

```bash
uv sync                      # install dependencies
./run.sh                     # start server (cd backend && uv run uvicorn app:app --reload --port 8000)
cd backend && uv run uvicorn app:app --reload --port 8000   # manual start
```

- Always use `uv` to run the server and manage all dependencies. Do not use `pip`.
  - Add or remove packages with `uv add <pkg>` / `uv remove <pkg>`, so `pyproject.toml` and `uv.lock` stay in sync. Don't edit `pyproject.toml` by hand to change dependencies.
  - Run any Python script with `uv run`, not bare `python`.
- Needs `ANTHROPIC_API_KEY` in `starting-codebase/.env` (loaded by `python-dotenv` in `backend/config.py`).
- UI at http://localhost:8000, API docs at http://localhost:8000/docs.
- The server must be started from `backend/` because `app.py` uses relative paths (`../docs`, `../frontend`, `./chroma_db`).
- There are no tests, linter or build step configured.

## Architecture

FastAPI backend (`backend/`) that also serves the static frontend (`frontend/`) at `/`. A query flows through these layers:

`frontend/script.js` → `POST /api/query` (`app.py`) → `RAGSystem.query` (`rag_system.py`) → `AIGenerator` (`ai_generator.py`) → Claude → `ToolManager`/`CourseSearchTool` (`search_tools.py`) → `VectorStore` (`vector_store.py`, ChromaDB).

Key design points that span multiple files:

- **Retrieval is tool-based, not automatic.** Claude decides whether to call the `search_course_content` tool (params: `query`, optional `course_name`, `lesson_number`). `AIGenerator` makes up to two Claude calls: the first with tools, and if it returns `tool_use`, a second without tools that carries the tool results. The system prompt limits it to one search per query. Only one tool round is handled.
- **Sources for the UI** are a side channel: `CourseSearchTool.last_sources` is filled during the search, then read and reset by `RAGSystem.query` after the response. If Claude doesn't search, `sources` is empty.
- **Two Chroma collections** in `VectorStore`: `course_catalog` (one doc per course, id = title, used for fuzzy course-name resolution via vector search) and `course_content` (chunks, with `course_title`/`lesson_number` metadata used for `where` filters).
- **Ingestion** happens at startup (`app.py` startup event → `add_course_folder("../docs")`). Existing courses are skipped, so editing a doc already ingested has no effect until `backend/chroma_db/` is cleared or `clear_existing=True` is used. `DocumentProcessor` expects this format: `Course Title:`, `Course Link:`, `Course Instructor:` on the first lines, then `Lesson N: title` markers with an optional `Lesson Link:` line. Text is chunked by sentence, with `CHUNK_SIZE=800` and `CHUNK_OVERLAP=100` characters.
- **Chunk prefixes are inconsistent:** the last lesson's chunks all get a `Course <title> Lesson N content:` prefix, while earlier lessons only prefix the first chunk with `Lesson N content:` (`document_processor.py`).
- **Sessions** are in-memory (`session_manager.py`), and history is limited to `MAX_HISTORY=2` messages.
- **Settings** (model `claude-sonnet-4-20250514`, embedding model `all-MiniLM-L6-v2`, `MAX_RESULTS=5`, paths) are all in `backend/config.py`. Claude calls use `temperature=0` and `max_tokens=800`.

## Diagrams

Per `.github/instructions/mermaid.instructions.md`, write diagrams as `.mmd` files. The query-flow sequence diagram is at `starting-codebase/docs/query-flow.mmd`.
