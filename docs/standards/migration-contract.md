# Migration Contract Standard

- Service: `lotus-ai`
- Persistence mode: Alembic-managed relational schema.
- Migration policy: versioned, deterministic, forward-only in production.

## Deterministic Checks

- `make migration-smoke` validates migration inventory and executes:
  - `python -m alembic heads`
  - `python -m alembic upgrade head --sql`
- CI executes `make migration-smoke` on each PR.

## Apply Command

- `make migration-apply` executes `python -m alembic upgrade head`.

## Rollback and Forward-Fix

- Production rollback is forward-fix oriented; never edit applied migration files.
- If migration issues are found, publish a new corrective migration revision.

## Runtime Responsibility Split

- `lotus-ai` owns migration files, schema review, and migration contract validation.
- Repository adapters must assume schema exists and must not create tables implicitly at runtime.
- Local development and CI may use SQLite for fast validation, but the migration contract remains Alembic-managed.
