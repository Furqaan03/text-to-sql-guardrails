"""Guardrail middleware: block anything that isn't a bounded read query.

Every rule is configurable and every block is logged with a reason. This layer
is the compliance gate — it's what makes a text-to-SQL system approvable."""
from __future__ import annotations

import re
from dataclasses import dataclass

import sqlparse
from sqlparse.sql import Token
from sqlparse.tokens import DML, Keyword

_DDL = {"CREATE", "ALTER", "DROP", "TRUNCATE", "RENAME"}
_DML_WRITE = {"INSERT", "UPDATE", "DELETE", "MERGE", "REPLACE", "UPSERT"}
_DANGEROUS = {"GRANT", "REVOKE", "ATTACH", "DETACH", "PRAGMA", "VACUUM"}


@dataclass
class GuardrailConfig:
    default_row_limit: int = 1000
    max_subquery_depth: int = 3
    allow_only_select: bool = True


@dataclass
class GuardrailResult:
    allowed: bool
    reason: str = ""
    rewritten_sql: str = ""


def _first_dml_keyword(statement) -> str | None:
    for token in statement.flatten():
        if token.ttype is DML:
            return token.value.upper()
    return None


def _has_keyword(sql_upper: str, words: set[str]) -> bool:
    return any(re.search(rf"\b{w}\b", sql_upper) for w in words)


def _subquery_depth(sql: str) -> int:
    depth = max_depth = 0
    for ch in sql:
        if ch == "(":
            depth += 1
            max_depth = max(max_depth, depth)
        elif ch == ")":
            depth = max(0, depth - 1)
    return max_depth


def _enforce_row_limit(sql: str, limit: int) -> str:
    if re.search(r"\bLIMIT\b", sql, re.IGNORECASE):
        return sql
    return sql.rstrip().rstrip(";") + f" LIMIT {limit}"


def check_sql(sql: str, config: GuardrailConfig | None = None) -> GuardrailResult:
    config = config or GuardrailConfig()
    sql_stripped = sql.strip()
    sql_upper = sql_stripped.upper()

    statements = sqlparse.parse(sql_stripped)
    if len(statements) != 1:
        return GuardrailResult(False, "Multiple statements are not allowed (possible injection).")

    statement = statements[0]

    if _has_keyword(sql_upper, _DDL):
        return GuardrailResult(False, "DDL statements (CREATE/ALTER/DROP/TRUNCATE) are blocked.")
    if _has_keyword(sql_upper, _DML_WRITE):
        return GuardrailResult(False, "Write statements (INSERT/UPDATE/DELETE) are blocked.")
    if _has_keyword(sql_upper, _DANGEROUS):
        return GuardrailResult(False, "Privileged/meta statements (GRANT/PRAGMA/ATTACH/...) are blocked.")

    dml = _first_dml_keyword(statement)
    if config.allow_only_select and dml != "SELECT":
        return GuardrailResult(False, f"Only SELECT queries are allowed (got {dml or 'non-SELECT'}).")

    if _subquery_depth(sql_stripped) > config.max_subquery_depth:
        return GuardrailResult(False, f"Subquery nesting exceeds max depth {config.max_subquery_depth}.")

    rewritten = _enforce_row_limit(sql_stripped, config.default_row_limit)
    return GuardrailResult(True, "ok", rewritten_sql=rewritten)
