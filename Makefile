.PHONY: dev down logs api-install api-check api-test seed-demo web-install web-check migrate migration ship-rehearsal

dev:
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f web api worker

api-install:
	cd apps/api && python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'

api-check:
	cd apps/api && .venv/bin/ruff check . && .venv/bin/python -m py_compile scripts/legacy_migration.py && .venv/bin/mypy src && .venv/bin/pytest

api-test:
	cd apps/api && .venv/bin/pytest

seed-demo:
	@test -n "$$DEMO_DATA_PASSWORD" || (echo "Set DEMO_DATA_PASSWORD first" && exit 1)
	docker compose exec -e DEMO_DATA_PASSWORD api python -m utag_api.cli seed-demo

web-install:
	pnpm install --frozen-lockfile

web-check:
	pnpm check

migrate:
	cd apps/api && .venv/bin/alembic upgrade head

migration:
	cd apps/api && .venv/bin/alembic revision --autogenerate -m "$(name)"

ship-rehearsal:
	@test -n "$$LEGACY_DATABASE_URL" || (echo "Set LEGACY_DATABASE_URL first" && exit 1)
	ops/scripts/ship-production.sh --mode rehearsal
