import pytest
from sqlalchemy import create_engine, text

from src.safety.execute import execute_readonly
from src.validation.hallucination import result_sanity_check


@pytest.fixture()
def engine():
    eng = create_engine("sqlite:///:memory:")
    with eng.begin() as conn:
        conn.execute(text("CREATE TABLE t (id INTEGER, name TEXT)"))
        conn.execute(text("INSERT INTO t VALUES (1, 'a'), (2, 'b')"))
    return eng


def test_readonly_returns_rows(engine):
    result = execute_readonly(engine, "SELECT * FROM t ORDER BY id")
    assert result.row_count == 2
    assert result.rows[0]["name"] == "a"


def test_readonly_rolls_back_writes(engine):
    # Even if a write sneaks through, the rollback guarantees no persistence.
    execute_readonly(engine, "INSERT INTO t VALUES (3, 'c')")
    after = execute_readonly(engine, "SELECT COUNT(*) AS n FROM t")
    assert after.rows[0]["n"] == 2  # insert was rolled back


def test_error_is_captured(engine):
    result = execute_readonly(engine, "SELECT * FROM nonexistent_table")
    assert result.error is not None
    assert result.row_count == 0


def test_result_sanity_flags_error():
    from src.safety.execute import ExecutionResult

    sane, note = result_sanity_check(ExecutionResult(rows=[], row_count=0, execution_ms=1.0, error="boom"))
    assert sane is False
