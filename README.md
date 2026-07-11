# Text-to-SQL with Guardrails and Hallucination Detection

A natural-language interface to a real SQL database that translates English into
SQL, executes it safely behind guardrails that block every destructive
operation, verifies the generated SQL actually answers the question asked, and
returns results with a confidence score.

## Why this exists

Text-to-SQL is one of the highest-value enterprise LLM applications and
notoriously hard to ship safely. Building one with guardrails and hallucination
detection proves you can ship AI a compliance team would approve — the real bar
for production AI.

## Architecture

```
src/schema/introspect.py       SQLAlchemy schema introspection -> LLM context
                                (tables, columns, FKs, sample categorical values)
src/generation/generate.py     NL -> structured SQL (sql, explanation, confidence,
                                tables_used) + syntax validation
src/safety/guardrails.py       the compliance gate: blocks DDL/DML-writes/privileged
                                statements, rejects multi-statement injections and
                                deep subqueries, enforces a row limit; every block logged
src/safety/execute.py          read-only sandbox: runs inside a transaction that ALWAYS
                                rolls back — a second line of defense below the guardrails
src/validation/hallucination.py  back-translation alignment, result sanity checks,
                                  composite confidence scoring
src/api/main.py                FastAPI: /v1/query (generate->guard->execute->validate)
```

## Design decisions

- **Defense in depth: guardrails AND a read-only sandbox.** The guardrail layer
  blocks anything that isn't a bounded SELECT (DDL, writes, GRANT/PRAGMA, multi-
  statement injections, over-deep subqueries). Even if something slips past, every
  query runs inside a transaction that is *always rolled back* — so a write can
  never persist. Two independent layers, because "the LLM shouldn't write" isn't a
  safety guarantee on its own.
- **Parsing, not just regex.** Statement structure is checked with `sqlparse`
  (statement count, first DML keyword, type) rather than trusting string matching
  alone, so `SELECT 1; DROP TABLE x` is caught as two statements.
- **Hallucination detection via back-translation.** After generating SQL, the
  system asks a model "what question does this query answer?" and scores alignment
  to the original. Low alignment means the SQL is syntactically fine but answers the
  wrong question — the failure mode raw execution can't catch.
- **Result sanity checks are free (no LLM).** Empty sets, execution errors, and
  NULL-heavy first rows (a bad-JOIN signature) are flagged structurally.
- **Confidence is a composite of independent signals** (syntax validity, back-
  translation alignment, result sanity, schema coverage) — displayed with every
  result so a low-confidence answer is visibly low-confidence.

## Setup

```bash
python -m venv .venv
.venv/Scripts/activate
pip install -r requirements.txt
cp .env.example .env       # OPENAI_API_KEY
python -m src.seed_db      # creates data/demo.db (customers, orders)
uvicorn src.api.main:app --reload
```

## Example

```bash
curl -X POST localhost:8000/v1/query -H "Content-Type: application/json" \
  -d '{"question": "total paid order amount per enterprise customer"}'
# -> {"sql": "SELECT ... LIMIT 1000", "rows": [...], "confidence": {"composite": 0.9, ...}}

curl -X POST localhost:8000/v1/query -d '{"question": "delete all orders"}' -H "Content-Type: application/json"
# -> {"blocked": true, "reason": "Write statements (INSERT/UPDATE/DELETE) are blocked."}
```

## Tests

```bash
pytest tests/ -v
```

17 tests covering the full guardrail matrix (allows SELECT + adds LIMIT; blocks
DROP/DELETE/UPDATE/INSERT/PRAGMA/GRANT/multi-statement/deep-subquery; preserves
existing LIMIT; configurable row cap), the read-only sandbox (returns rows, rolls
back writes, captures errors), and confidence scoring — all offline, no API key.

## Docker

```bash
docker build -t text-to-sql . && docker run -p 8000:8000 --env-file .env text-to-sql
```

## Status

Phases 1-3 complete (schema-aware generation, guardrails + read-only sandbox,
hallucination detection + confidence) plus the query API. Phase 4's frontend and
Phase 5's 50-question golden eval suite are not built; the guardrail matrix is
the tested core.
