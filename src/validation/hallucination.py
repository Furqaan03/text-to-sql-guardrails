"""Hallucination detection: back-translation alignment, result sanity, composite confidence."""
from __future__ import annotations

import json

from openai import OpenAI
from pydantic import BaseModel

from src.safety.execute import ExecutionResult


class ConfidenceBreakdown(BaseModel):
    syntax_valid: bool
    back_translation_alignment: float   # 0-1
    result_sane: bool
    schema_coverage: bool
    composite: float


def back_translate(sql: str, original_question: str, client: OpenAI | None = None) -> float:
    """Ask the model what question the SQL answers, then score alignment to the original.
    Divergence means the SQL probably doesn't answer what was asked."""
    client = client or OpenAI()
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "user", "content": (
                f"SQL query:\n{sql}\n\nWhat natural-language question does this query answer? "
                f"Then rate 0-1 how well it matches this original question: '{original_question}'. "
                'Respond as JSON: {"back_question": "...", "alignment": 0.0-1.0}.'
            )},
        ],
        response_format={"type": "json_object"},
        temperature=0,
    )
    return float(json.loads(resp.choices[0].message.content or "{}").get("alignment", 0.5))


def result_sanity_check(result: ExecutionResult) -> tuple[bool, str]:
    """Cheap structural sanity checks — no LLM."""
    if result.error:
        return False, f"execution error: {result.error}"
    if result.row_count == 0:
        return True, "empty result set (valid but worth noting)"
    # Flag NULL-heavy results that often indicate a bad JOIN.
    first = result.rows[0]
    null_ratio = sum(1 for v in first.values() if v is None) / max(1, len(first))
    if null_ratio > 0.5:
        return False, "over half the columns are NULL — possible bad JOIN"
    return True, "ok"


def compute_confidence(
    syntax_valid: bool,
    back_alignment: float,
    result_sane: bool,
    schema_coverage: bool,
) -> ConfidenceBreakdown:
    signals = [
        1.0 if syntax_valid else 0.0,
        back_alignment,
        1.0 if result_sane else 0.0,
        1.0 if schema_coverage else 0.0,
    ]
    composite = round(sum(signals) / len(signals), 3)
    return ConfidenceBreakdown(
        syntax_valid=syntax_valid,
        back_translation_alignment=round(back_alignment, 3),
        result_sane=result_sane,
        schema_coverage=schema_coverage,
        composite=composite,
    )
