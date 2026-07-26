.PHONY: backend-start backend-worker pipeline-worker backend-infra backend-migrate backend-migration backend-unit backend-integration backend-format backend-quality

backend-start:
	cd apps/api && uvicorn vip_api.main:app --reload --no-access-log

backend-worker:
	cd apps/api && python -m vip_api.jobs.worker

pipeline-worker:
	cd apps/api && python -m vip_api.pipelines.worker

backend-infra:
	docker compose up -d postgres redis

backend-migrate:
	cd apps/api && alembic upgrade head

backend-migration:
	cd apps/api && alembic revision --autogenerate -m "$(NAME)"

backend-unit:
	cd apps/api && pytest -m "not integration"

backend-integration:
	cd apps/api && RUN_INTEGRATION_TESTS=1 pytest -m integration

backend-format:
	cd apps/api && ruff check . --fix && ruff format .

backend-quality:
	cd apps/api && python scripts/backend_quality.py
