"""FastAPI: NL question -> generate SQL -> guardrail -> sandboxed execute -> validate."""
from __future__ import annotations

import os

from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel
from sqlalchemy import create_engine

from src.generation.generate import generate_sql, is_valid_syntax
from src.safety.execute import execute_readonly
from src.safety.guardrails import GuardrailConfig, check_sql
from src.schema.introspect import introspect_schema, schema_to_prompt
from src.validation.hallucination import back_translate, compute_confidence, result_sanity_check

load_dotenv()

app = FastAPI(title="Text-to-SQL with Guardrails")
_engine = None
_schema_cache: str | None = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(os.getenv("DATABASE_URL", "sqlite:///./data/demo.db"))
    return _engine


def get_schema_text() -> str:
    global _schema_cache
    if _schema_cache is None:
        _schema_cache = schema_to_prompt(introspect_schema(get_engine()))
    return _schema_cache


class QueryRequest(BaseModel):
    question: str


@app.post("/v1/query")
def query(req: QueryRequest) -> dict:
    generated = generate_sql(req.question, get_schema_text())

    guardrail = check_sql(generated.sql, GuardrailConfig())
    if not guardrail.allowed:
        return {"blocked": True, "reason": guardrail.reason, "sql": generated.sql}

    safe_sql = guardrail.rewritten_sql
    result = execute_readonly(get_engine(), safe_sql)

    alignment = back_translate(safe_sql, req.question)
    result_sane, sanity_note = result_sanity_check(result)
    confidence = compute_confidence(
        syntax_valid=is_valid_syntax(safe_sql),
        back_alignment=alignment,
        result_sane=result_sane,
        schema_coverage=bool(generated.tables_used),
    )

    return {
        "blocked": False,
        "sql": safe_sql,
        "explanation": generated.explanation,
        "rows": result.rows,
        "row_count": result.row_count,
        "execution_ms": result.execution_ms,
        "error": result.error,
        "sanity_note": sanity_note,
        "confidence": confidence.model_dump(),
    }


@app.get("/v1/schema")
def schema() -> dict:
    return {"schema": get_schema_text()}
