# AGENTS.md

Agent guide for working in the Jackgram repository.

## Project Snapshot

- Language: Python (runtime in Dockerfile is 3.11; README states 3.8+).
- Core stack: FastAPI + Uvicorn, Telethon, Motor (MongoDB async client).
- App entry point: `python -m jackgram`.
- Services: HTTP API + Telegram bot run concurrently in one asyncio loop.
- Main package: `jackgram/`.

## Repository Rules Sources

- Cursor rules: not found (`.cursor/rules/` and `.cursorrules` absent).
- Copilot rules: not found (`.github/copilot-instructions.md` absent).
- If these files are added later, treat them as higher-priority local instructions.

## Setup Commands

- Create venv (recommended): `python3 -m venv venv`.
- Activate venv: `source venv/bin/activate`.
- Install dependencies: `pip install -r requirements.txt`.
- Prepare config: `cp sample_config.env config.env`.
- Fill required env vars in `config.env` before running services.

## Run / Build Commands

- Run locally: `python3 -m jackgram`.
- Alternative start script: `bash start.sh`.
- Docker build: `docker compose build`.
- Docker run (app + mongo): `docker compose up -d`.
- Docker run with rebuild: `docker compose up -d --build`.
- View logs: `docker compose logs -f app`.

## Test Commands (Pytest)

- Run full test suite: `pytest`.
- Quiet mode: `pytest -q`.
- Stop on first failure: `pytest -x`.
- Verbose with print/log output: `pytest -vv -s`.

### Run a Single Test File

- `pytest tests/test_scraping_filters.py`
- `pytest tests/test_ptt_parsing.py`
- `pytest tests/test_database.py`

### Run a Single Test Function

- `pytest tests/test_scraping_filters.py::test_get_file_extension`
- `pytest tests/test_database.py::test_add_tmdb`

### Run a Subset by Name Pattern

- `pytest -k "minimum" tests/test_scraping_filters.py`
- `pytest -k "ptt_fields" tests/test_ptt_parsing.py`

### Test Environment Notes

- `tests/test_database.py` expects MongoDB at `mongodb://localhost:27017`.
- Start local MongoDB before DB tests, or use Docker (`docker compose up -d mongo`).
- Async tests use `pytest-asyncio`; keep test functions `async def` when needed.

## Lint / Formatting Commands

This repo currently has no committed lint config (`ruff`, `black`, `flake8`, `mypy`, `pyproject.toml`, `setup.cfg`, `tox.ini` not present).

Use these safe checks unless/until a formal linter is added:

- Syntax check project: `python -m compileall jackgram tests`
- Basic dead-import scan (if available in your env): `python -m pip check`

If you introduce a linter/formatter in a PR, document commands here and add config files in the same PR.

## Code Style: Follow Existing Conventions

### Imports

- Prefer standard-library imports first, then third-party, then local package imports.
- Existing files are not perfectly uniform; for touched files, improve order without broad churn.
- Use explicit imports for frequently used symbols (e.g., `from typing import Dict, Any`).
- Avoid wildcard imports.

### Formatting

- Follow PEP 8 with pragmatic consistency to nearby code.
- Use 4 spaces; no tabs.
- Keep lines readable (target ~88-100 chars, but prioritize local consistency).
- Use blank lines to separate logical blocks and route groups.
- Prefer double quotes where existing file does.

### Types

- Add type hints for new/changed functions where practical.
- Follow current typing style: `Dict[str, Any]`, `Optional[T]`, `List[T]`.
- For async DB/API boundaries, annotate return types explicitly.
- Do not block changes on full strict typing; this codebase is partially typed.

### Naming

- Functions/variables: `snake_case`.
- Classes: `PascalCase`.
- Constants/env-derived settings: `UPPER_SNAKE_CASE` (see `jackgram/bot/bot.py`).
- Test files: `tests/test_*.py`; test functions: `test_*`.

### Async and Concurrency

- Prefer `async def` for I/O-bound operations (DB calls, HTTP calls, Telegram client calls).
- Use `await` consistently; avoid blocking calls in async paths.
- Reuse existing concurrency primitives (`asyncio.Lock`, tasks, cancellation events).
- Preserve cancellation handling in stream-related code paths.

### FastAPI / API Patterns

- Keep routes grouped by concern (`routes.py`, `server/api/*.py`).
- Validate query params using `fastapi.Query` constraints where appropriate.
- Raise `HTTPException` with clear status codes and short actionable messages.
- Use `Depends(...)` for auth/token verification.
- For response shaping, keep Mongo `_id` out of public payloads.

### Database Patterns

- Use `Database` helper in `jackgram/utils/database.py` rather than ad hoc DB access.
- Keep operations async via Motor.
- Prefer existing update/merge helpers for movie/series file info updates.
- Preserve duplicate-prevention logic (hash + name/size checks).

### Error Handling and Logging

- Catch narrow exceptions where behavior is known (e.g., Telegram API errors).
- Use broad `except Exception` only at API/service boundaries with safe fallback.
- Log context-rich messages (`logging.info/warning/error`) without leaking secrets.
- For HTTP handlers, convert internal errors into proper `HTTPException` responses.

### Configuration and Secrets

- Read config from `config.env` via environment variables.
- Never hardcode real tokens, API keys, or session strings.
- Keep defaults safe and development-friendly when possible.

### Testing Conventions

- Prefer deterministic unit tests with focused fixtures/helpers.
- Use `pytest.mark.parametrize` for input matrix tests.
- For async tests, mark with `@pytest.mark.asyncio`.
- Keep test names descriptive of behavior.

## Scope and Change Discipline

- Make minimal, targeted changes; avoid unrelated refactors.
- Preserve public API response shapes unless intentionally changing contract.
- When modifying streaming/indexing flows, keep backward compatibility in mind.
- Update README and this file when build/test workflows change.

## Quick File Map

- App bootstrap: `jackgram/__main__.py`
- FastAPI app wiring: `jackgram/__init__.py`
- Main routes: `jackgram/server/routes.py`
- API modules: `jackgram/server/api/`
- Bot config/runtime: `jackgram/bot/bot.py`
- DB layer: `jackgram/utils/database.py`
- Tests: `tests/`
