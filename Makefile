.PHONY: frontend-install frontend-lint frontend-typecheck frontend-test frontend-build backend-start backend-worker pipeline-worker backend-infra backend-migrate backend-migration backend-unit backend-integration backend-format backend-quality docker-validate repository-security product-certification demo-reset

frontend-install:
	npm ci

frontend-lint:
	npm run lint

frontend-typecheck:
	npm run typecheck

frontend-test:
	npm run test

frontend-build:
	npm run build

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

docker-validate:
	docker compose config --quiet

repository-security:
	python scripts/certification/repository-security-audit.py --scope all

product-certification:
	python scripts/certification/collect-baseline.py

demo-reset:
	powershell -NoProfile -ExecutionPolicy Bypass -File scripts/demo/reset-demo-environment.ps1 -Mode Apply -ConfirmNonProduction -VerifiedBackupPath "$(BACKUP)"
