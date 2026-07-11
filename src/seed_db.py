"""Seeds a small SQLite demo database (customers, orders) for local testing."""
from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, text

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "demo.db"


def seed() -> None:
    DB_PATH.parent.mkdir(exist_ok=True)
    engine = create_engine(f"sqlite:///{DB_PATH}")
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS orders"))
        conn.execute(text("DROP TABLE IF EXISTS customers"))
        conn.execute(text("CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT, country TEXT, tier TEXT)"))
        conn.execute(text(
            "CREATE TABLE orders (id INTEGER PRIMARY KEY, customer_id INTEGER, amount REAL, status TEXT, "
            "order_date TEXT, FOREIGN KEY(customer_id) REFERENCES customers(id))"
        ))
        customers = [
            (1, "Acme Corp", "USA", "enterprise"),
            (2, "Globex", "UK", "smb"),
            (3, "Initech", "USA", "enterprise"),
        ]
        conn.execute(text("INSERT INTO customers VALUES (:a,:b,:c,:d)"),
                     [dict(a=a, b=b, c=c, d=d) for a, b, c, d in customers])
        orders = [
            (1, 1, 5000.0, "paid", "2026-01-15"),
            (2, 1, 2500.0, "pending", "2026-02-20"),
            (3, 2, 800.0, "paid", "2026-03-10"),
            (4, 3, 12000.0, "paid", "2026-03-25"),
        ]
        conn.execute(text("INSERT INTO orders VALUES (:a,:b,:c,:d,:e)"),
                     [dict(a=a, b=b, c=c, d=d, e=e) for a, b, c, d, e in orders])
    print(f"Seeded {DB_PATH}")


if __name__ == "__main__":
    seed()
