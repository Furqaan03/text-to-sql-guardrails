"""Sandboxed execution: read-only transaction that always rolls back."""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import Engine, text


@dataclass
class ExecutionResult:
    rows: list[dict]
    row_count: int
    execution_ms: float
    error: str | None = None


def execute_readonly(engine: Engine, sql: str, max_rows: int = 1000) -> ExecutionResult:
    """Runs SQL inside a transaction that is always rolled back — even a SELECT
    with a side-effecting function can't persist anything."""
    import time

    start = time.perf_counter()
    try:
        with engine.connect() as conn:
            trans = conn.begin()
            try:
                result = conn.execute(text(sql))
                rows = [dict(r._mapping) for r in result.fetchmany(max_rows)]
            finally:
                trans.rollback()  # never commit — read-only guarantee
        return ExecutionResult(rows=rows, row_count=len(rows), execution_ms=(time.perf_counter() - start) * 1000)
    except Exception as exc:  # noqa: BLE001 — surfaced to caller as a structured error
        return ExecutionResult(rows=[], row_count=0, execution_ms=(time.perf_counter() - start) * 1000, error=str(exc))
