.PHONY: install lint monetary-float-guard typecheck openapi-gate eval-manifest-gate eval-run-gate async-job-gate migration-smoke migration-apply runtime-mode-smoke test test-unit test-integration test-e2e test-coverage coverage-gate security-audit check ci docker-build clean

install:
	python -m pip install --upgrade pip
	python -m pip install -e ".[dev]"

lint:
	python -m ruff check .
	python -m ruff format --check .

monetary-float-guard:
	python scripts/check_monetary_float_usage.py

typecheck:
	python -m mypy --config-file mypy.ini

openapi-gate:
	python scripts/openapi_quality_gate.py

eval-manifest-gate:
	python scripts/validate_eval_fixture_manifest.py

eval-run-gate:
	python scripts/validate_eval_run_artifacts.py

async-job-gate:
	python scripts/validate_async_job_artifacts.py

migration-smoke:
	python scripts/migration_contract_check.py --mode alembic-sql

migration-apply:
	python -m alembic upgrade head

runtime-mode-smoke:
	python -m pytest tests/integration/test_runtime_modes.py -q

test:
	$(MAKE) test-unit

test-unit:
	python -m pytest tests/unit

test-integration:
	python -m pytest tests/integration

test-e2e:
	python -m pytest tests/e2e

test-coverage:
	COVERAGE_FILE=.coverage.unit python -m pytest tests/unit --cov=src --cov-report=
	COVERAGE_FILE=.coverage.integration python scripts/run_integration_coverage.py
	COVERAGE_FILE=.coverage.e2e python -m pytest tests/e2e --cov=src --cov-report=
	python -m coverage combine .coverage.unit .coverage.integration .coverage.e2e
	python -m coverage report --fail-under=99

security-audit:
	python scripts/run_security_audit.py

check: lint typecheck openapi-gate eval-manifest-gate eval-run-gate async-job-gate migration-smoke runtime-mode-smoke test

ci: lint typecheck openapi-gate eval-manifest-gate eval-run-gate async-job-gate migration-smoke runtime-mode-smoke test-integration test-e2e test-coverage security-audit

docker-build:
	docker build -t backend-service:ci-test .

clean:
	python -c "import shutil, pathlib; [shutil.rmtree(p, ignore_errors=True) for p in ['.pytest_cache', '.ruff_cache', '.mypy_cache']]; [pathlib.Path(p).unlink(missing_ok=True) for p in ['.coverage', '.coverage.unit', '.coverage.integration', '.coverage.e2e']]"


