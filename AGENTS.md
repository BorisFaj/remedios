# Repository Guidelines

## Project Structure & Module Organization
Core application code lives under `remedios/`:
- `remedios/core/api/`: internal API, persistence, and DB integration.
- `remedios/core/dispatcher/`: webhook intake and Kafka publishing.
- `remedios/consumers/text/`: text worker.
- `remedios/consumers/audio/whisper_turbo/`: supported audio transcription worker.
- `remedios/commons/`: shared schemas and utilities.
- `remedios/test/`: unit and integration tests (`integration/` for Oracle connectivity checks).

Infrastructure and deployment assets are in `zordon/`:
- `zordon/ansible/`: cluster and service playbooks.
- `zordon/deploy/`: Kubernetes manifests.

DB migrations are in `migrations/`; supporting docs and scripts are in `docs/` and `scripts/`.

## Build, Test, and Development Commands
- `python -m pip install -r requirements_dev.txt`: install dev/lint/test tooling.
- `pip install -r remedios/core/api/requirements.txt` (and consumer `requirements.txt` files): install service-specific deps.
- `python -m pytest -q remedios/test/test_persistence_storage.py remedios/test/test_consumers_processing.py`: run core CI unit tests.
- `python -m pytest -q remedios/test`: run full Python test suite.
- `python -m ruff check --select F401 .`: run the repo’s CI lint rule (unused imports).
- `./scripts/alembic-oracle.sh upgrade head`: apply Alembic migrations with env loaded from `zordon/.secrets`.

## Coding Style & Naming Conventions
Use 4-space indentation in Python and follow PEP 8 naming:
- modules/files: `snake_case.py`
- functions/variables: `snake_case`
- classes: `PascalCase`
- constants/env vars: `UPPER_SNAKE_CASE`

Keep service boundaries clear (API vs dispatcher vs consumers). Prefer small, explicit functions and shared types in `remedios/commons/schemas.py` where applicable.

## Testing Guidelines
Framework: `pytest`. Name tests as `test_*.py` and test functions as `test_*`.
Place unit tests in `remedios/test/` and integration checks in `remedios/test/integration/`.
For Oracle-dependent tests, guard with skips when required `ORACLE_*` vars/wallet are missing (current pattern in integration tests).

## Commit & Pull Request Guidelines
Recent history favors short, imperative commit subjects (e.g., `Fix CI requirements_dev.txt path`, `Add pytest/ruff to dev requirements`).
- Keep subject lines concise and action-focused.
- Group related changes per commit; avoid mixing infra and app refactors unless necessary.

PRs should:
- target `develop`,
- describe behavioral impact and config/env changes,
- link issues (if any),
- include logs/screenshots for deployment or runtime changes,
- pass `pytest` and `ruff` checks before review.
