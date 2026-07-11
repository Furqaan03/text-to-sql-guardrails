"""Schema introspection via SQLAlchemy — builds the context the LLM writes SQL against."""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import Engine, inspect, text


@dataclass
class ColumnInfo:
    name: str
    type: str


@dataclass
class TableInfo:
    name: str
    columns: list[ColumnInfo] = field(default_factory=list)
    foreign_keys: list[str] = field(default_factory=list)
    sample_values: dict[str, list] = field(default_factory=dict)


def introspect_schema(engine: Engine, sample_categorical: bool = True) -> list[TableInfo]:
    inspector = inspect(engine)
    tables = []
    for table_name in inspector.get_table_names():
        cols = [ColumnInfo(c["name"], str(c["type"])) for c in inspector.get_columns(table_name)]
        fks = [
            f"{table_name}.{fk['constrained_columns'][0]} -> {fk['referred_table']}.{fk['referred_columns'][0]}"
            for fk in inspector.get_foreign_keys(table_name)
            if fk.get("constrained_columns") and fk.get("referred_columns")
        ]
        info = TableInfo(name=table_name, columns=cols, foreign_keys=fks)
        if sample_categorical:
            info.sample_values = _sample_values(engine, table_name, cols)
        tables.append(info)
    return tables


def _sample_values(engine: Engine, table: str, cols: list[ColumnInfo], limit: int = 3) -> dict[str, list]:
    """Grabs a few distinct values from low-cardinality text columns for disambiguation."""
    samples: dict[str, list] = {}
    with engine.connect() as conn:
        for col in cols:
            if "CHAR" in col.type.upper() or "TEXT" in col.type.upper():
                try:
                    rows = conn.execute(
                        text(f"SELECT DISTINCT {col.name} FROM {table} LIMIT {limit}")
                    ).fetchall()
                    samples[col.name] = [r[0] for r in rows]
                except Exception:  # noqa: BLE001 — sampling is best-effort context, never fatal
                    continue
    return samples


def schema_to_prompt(tables: list[TableInfo]) -> str:
    """Renders the schema as compact text for the SQL-generation prompt."""
    lines = []
    for t in tables:
        cols = ", ".join(f"{c.name} {c.type}" for c in t.columns)
        lines.append(f"TABLE {t.name} ({cols})")
        for fk in t.foreign_keys:
            lines.append(f"  FK: {fk}")
        for col, vals in t.sample_values.items():
            if vals:
                lines.append(f"  {col} sample values: {vals}")
    return "\n".join(lines)
