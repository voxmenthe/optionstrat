# Root uv Migration (Option B) — Plan

Date: 2026-01-30
Owner: Codex (assistant)
Status: Completed (Phases 1-4 complete)
Scope: Move uv project to repo root; keep backend code in `src/backend/`.

## Goal
Make it easy to run the security scan and backend without `cd src/backend` by moving the uv project (and `.venv`) to the repo root, while **preserving current DB behavior** and **keeping frontend+backend linked and standalone CLI workflows working**.

## Current State (Key Facts)
- uv project lives in `src/backend/` with `pyproject.toml` and `uv.lock`.
- Backend package root is `src/backend/app/` and imports use `app.*`.
- `options.db` is referenced via relative path `./options.db` in `src/backend/app/models/database.py` and `src/backend/app/db_upgrade.py`.
- `security_scan.db` is anchored to the backend directory via `Path(__file__).resolve().parents[2]`.
- Several scripts and Docker build context assume `src/backend` is the project root.
- There is an existing repo root `.venv`, but uv currently manages the backend `.venv`.

## Desired End State
- Repo root is the uv project root (`pyproject.toml`, `uv.lock`, `.venv`).
- Running from repo root works:
  - `uv run python -m app.security_scan.cli` (no `cd src/backend`).
  - Optional: `uv run security-scan` via `[project.scripts]`.
- Backend and frontend still run together (e.g., `run_app.sh`), and Docker still works.
- `options.db` and `security_scan.db` stay in `src/backend/` (current behavior preserved).

## Design Choices (Option B Details)
### Packaging / Imports
- Add build system and use **uv build backend** to install `app` as a package into the root uv environment.
- Configure:
  - `module-root = "src/backend"`
  - `module-name = "app"`
- Ensure `src/backend/app/__init__.py` exists (added).

### Database Paths (Preserve Current Behavior)
- **Keep DBs in `src/backend/`** and make paths robust to working directory:
  - Replace `sqlite:///./options.db` with a path anchored to `src/backend`.
  - Update `db_upgrade.py` to resolve the DB path in the same way.
  - Update `security_scan/cli.py` to compute `options.db` relative to backend root (not `Path.cwd()`).

### Scripts / Tooling / Docs
- Update scripts and docs that assume `cd src/backend` or backend-local `pyproject.toml`:
  - `run_app.sh` -> run `uv sync` and `uv run python -m app.main` from repo root.
  - `src/backend/project_setup.sh` -> either move to root or update to run with correct paths.
  - `src/backend/run_tests.sh`, `run_all_tests.sh`, `run_test_with_mock.sh` -> run from repo root (ensure `uv run` still works).
  - `src/backend/README.md`, `src/backend/tests/README.md`, and `src/backend/app/security_scan/README.md` -> update commands.
  - `src/backend/notebooks/indicator_sanity_check.py` -> update comments and preferred venv path to root `.venv` (logic may already work; check).

### Docker / Compose
- Update `src/backend/Dockerfile` to expect root `pyproject.toml` and `uv.lock`.
- Update `docker-compose.yml` backend build context to repo root.
- Ensure runtime command still uses `uvicorn app.main:app` and that code is copied correctly.

## Work Breakdown

### Phase 1 — Move uv Project to Root
1. **Create root `pyproject.toml`:** [x]
   - Move `src/backend/pyproject.toml` to repo root. [x]
   - Add build system with `uv_build` and `tool.uv.build-backend` config. [x]
   - Adjust `readme` path to `src/backend/README.md` (or copy / move README to root). [x]
   - Keep dependencies and `[dependency-groups]` unchanged. [x]
2. **Move `uv.lock` to root.** [x]
3. **Remove/Archive** `src/backend/pyproject.toml` and `src/backend/uv.lock` (delete to avoid confusion). [x]

### Phase 2 — Path & DB Correctness
4. **Fix `options.db` pathing**: [x]
   - `src/backend/app/models/database.py`: compute base dir from file location, use absolute sqlite URL. [x]
   - `src/backend/app/db_upgrade.py`: compute base dir from file location; use absolute path. [x]
5. **Fix `security_scan` storage usage pathing**: [x]
   - `src/backend/app/security_scan/cli.py`: replace `Path.cwd()` for DB size with backend root (same as db path). [x]
6. **Anchor backend `.env` loading to backend root**: [x]
   - `src/backend/app/main.py`: load dotenv from `src/backend/.env` regardless of CWD. [x]

### Phase 3 — Scripts + Docs + CLI Ergonomics
6. **Update scripts** to assume root uv project:
   - `run_app.sh` [x]
   - `src/backend/project_setup.sh` [x]
   - `src/backend/run_tests.sh` [x]
   - `src/backend/run_all_tests.sh` [x]
   - `src/backend/run_test_with_mock.sh` [x]
7. **Update docs**:
   - `src/backend/README.md` [x]
   - `src/backend/tests/README.md` [x]
   - `src/backend/tests/integration_tests/README.md` [x]
   - `src/backend/app/security_scan/README.md` [x]
   - `README.md` (repo root) [x]
8. **Optional:** add `[project.scripts]` entry `security-scan = "app.security_scan.cli:main"` for a one-liner `uv run security-scan`. [x]

### Phase 4 — Docker / Compose
9. **Update `src/backend/Dockerfile`** to copy root `pyproject.toml` and `uv.lock`. [x]
10. **Update `docker-compose.yml`** backend context to `.` and Dockerfile path to `src/backend/Dockerfile`. [x]
11. Validate that mounting `./src/backend:/app` still works or adjust to mount repo root with correct `WORKDIR`. [x]

## Validation Plan
- From repo root:
  - `uv sync`
  - `uv run python -m app.security_scan.cli --help`
  - `uv run python -m app.main` (or via `run_app.sh`)
  - `uv run pytest src/backend/tests/test_security_scan.py`
- Docker sanity check (optional):
  - `docker compose build backend`
  - `docker compose up backend` and hit `/docs`.

## Risks / Mitigations
- **Import errors** if `app` is not packaged correctly. Mitigate by ensuring `uv_build` settings (`module-root`, `module-name`) match folder structure and `__init__.py` exists.
- **Silent DB relocation** if relative paths are still used. Mitigate by anchoring DB path to backend root.
- **Docker build fail** if lockfile not at expected path. Mitigate by updating Dockerfile + compose context.
- **Script drift** if some scripts still `cd src/backend`. Mitigate by updating all in Phase 3.

## Files Expected to Change
- `pyproject.toml` (new at repo root)
- `uv.lock` (move to repo root)
- Delete: `src/backend/pyproject.toml`, `src/backend/uv.lock`
- `src/backend/app/models/database.py`
- `src/backend/app/db_upgrade.py`
- `src/backend/app/security_scan/cli.py`
- `run_app.sh`
- `src/backend/project_setup.sh`
- `src/backend/run_tests.sh`
- `src/backend/run_all_tests.sh`
- `src/backend/run_test_with_mock.sh`
- `src/backend/README.md`
- `src/backend/tests/README.md`
- `src/backend/app/security_scan/README.md`
- `src/backend/Dockerfile`
- `docker-compose.yml`

## Out of Scope
- Refactoring backend code structure or moving files out of `src/backend/`.
- Changes to frontend build or tooling beyond wiring to backend.
