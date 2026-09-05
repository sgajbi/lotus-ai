.PHONY: install dependency-lock-replay-check lint module-budget-guard monetary-float-guard runtime-purity-guard verify-dependencies typecheck openapi-gate eval-manifest-gate eval-run-gate async-job-gate rfc0002-idea-proof-gate migration-smoke migration-apply data-lifecycle-run runtime-mode-smoke test test-unit test-integration test-e2e test-coverage coverage-gate security-audit check ci docker-build clean

install:
	python -m pip install --upgrade pip
	python -m pip install --require-hashes -r requirements-dev.lock.txt
	python -m pip install --no-deps -e .

# The audited dependency set is the installed set (issue #155): the lock must
# replay from pyproject byte-identically, or the build refuses.
dependency-lock-replay-check:
	uv lock --check
	uv export --format requirements-txt --no-emit-project -o requirements.lock.txt
	uv export --format requirements-txt --no-emit-project --extra dev -o requirements-dev.lock.txt
	git diff --exit-code -- uv.lock requirements.lock.txt requirements-dev.lock.txt

lint:
	python -m ruff check .
	python -m ruff format --check .
	python scripts/check_runtime_purity.py
	python scripts/check_monetary_float_usage.py
	python scripts/check_module_budget.py

monetary-float-guard:
	python scripts/check_monetary_float_usage.py

runtime-purity-guard:
	python scripts/check_runtime_purity.py

verify-dependencies:
	python scripts/dependency_health_check.py --skip-audit

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

rfc0002-idea-proof-gate:
	python scripts/generate_rfc0002_idea_explanation_proof.py

migration-smoke:
	python scripts/migration_contract_check.py --mode alembic-sql

migration-apply:
	python -m alembic upgrade head

data-lifecycle-run:
	python scripts/run_data_lifecycle.py

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
	python scripts/dependency_health_check.py

check: lint typecheck openapi-gate eval-manifest-gate eval-run-gate async-job-gate rfc0002-idea-proof-gate migration-smoke runtime-mode-smoke test

ci: verify-dependencies dependency-lock-replay-check lint typecheck openapi-gate eval-manifest-gate eval-run-gate async-job-gate rfc0002-idea-proof-gate migration-smoke runtime-mode-smoke security-audit test-coverage docker-build

docker-build:
	docker build -t backend-service:ci-test .
	docker run --rm backend-service:ci-test python -c "import os, importlib.util; assert os.getuid() == 10001, 'runtime image must not run as root'; assert all(importlib.util.find_spec(m) is None for m in ('pytest', 'mypy', 'ruff', 'pip_audit')), 'dev tooling leaked into the runtime image'; import app.main"
	-docker volume rm -f lotus-ai-ci-first-write
	docker run --rm -v lotus-ai-ci-first-write:/data backend-service:ci-test python -c "import pathlib; p = pathlib.Path('/data/object-store/first-write-proof'); p.write_text('ok'); assert p.read_text() == 'ok'; p.unlink()" && docker volume rm lotus-ai-ci-first-write

clean:
	python -c "import shutil, pathlib; [shutil.rmtree(p, ignore_errors=True) for p in ['.pytest_cache', '.ruff_cache', '.mypy_cache']]; [pathlib.Path(p).unlink(missing_ok=True) for p in ['.coverage', '.coverage.unit', '.coverage.integration', '.coverage.e2e']]"


