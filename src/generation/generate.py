"""SQL generation with structured output + syntax validation."""
from __future__ import annotations

import json

import sqlparse
from openai import OpenAI
from pydantic import BaseModel


class GeneratedSQL(BaseModel):
    sql: str
    explanation: str
    confidence: float
    tables_used: list[str]


_SYSTEM = """You translate natural-language questions into a single read-only SQL SELECT
query against the given schema. Respond as JSON:
{"sql": "...", "explanation": "what it does", "confidence": 0.0-1.0, "tables_used": [...]}.
Never write INSERT/UPDATE/DELETE/DROP. If the question is ambiguous, pick the most
likely interpretation and lower your confidence."""


def generate_sql(question: str, schema_text: str, client: OpenAI | None = None) -> GeneratedSQL:
    client = client or OpenAI()
    resp = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": f"Schema:\n{schema_text}\n\nQuestion: {question}"},
        ],
        response_format={"type": "json_object"},
        temperature=0,
    )
    parsed = json.loads(resp.choices[0].message.content or "{}")
    return GeneratedSQL(
        sql=parsed.get("sql", ""),
        explanation=parsed.get("explanation", ""),
        confidence=float(parsed.get("confidence", 0.5)),
        tables_used=parsed.get("tables_used", []),
    )


def is_valid_syntax(sql: str) -> bool:
    parsed = sqlparse.parse(sql)
    return bool(parsed) and parsed[0].get_type() == "SELECT"
