.PHONY: setup generate check check-generated lint typecheck test test-intelligence test-research build migrate api worker ui
setup:
	uv sync --frozen
	npm ci --ignore-scripts
generate:
	npm run generate
lint:
	uv run ruff check backend tests scripts examples
	uv run ruff format --check backend tests scripts examples
	npm run lint
typecheck:
	uv run mypy
	npm run typecheck
test:
	uv run pytest -q
test-intelligence:
	uv run pytest tests/intelligence -q
test-research:
	uv run pytest tests/research -q
build:
	npm run build
check-generated:
	uv run python scripts/check_generated.py
check: lint typecheck test build check-generated
migrate:
	uv run python -m buildbox_router.storage
api:
	uv run uvicorn buildbox_router.api:create_app --factory --host 127.0.0.1 --port 8000
worker:
	uv run python -m buildbox_router.worker
ui:
	npm run dev
