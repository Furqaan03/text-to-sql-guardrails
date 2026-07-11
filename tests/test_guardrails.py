from src.safety.guardrails import GuardrailConfig, check_sql


def test_allows_plain_select():
    r = check_sql("SELECT name FROM customers WHERE tier = 'enterprise'")
    assert r.allowed is True
    assert "LIMIT 1000" in r.rewritten_sql


def test_blocks_drop():
    assert check_sql("DROP TABLE customers").allowed is False


def test_blocks_delete():
    assert check_sql("DELETE FROM orders WHERE id = 1").allowed is False


def test_blocks_update():
    assert check_sql("UPDATE customers SET tier = 'enterprise'").allowed is False


def test_blocks_insert():
    assert check_sql("INSERT INTO customers VALUES (9, 'x', 'US', 'smb')").allowed is False


def test_blocks_multiple_statements():
    assert check_sql("SELECT 1; DROP TABLE customers").allowed is False


def test_blocks_pragma_and_grant():
    assert check_sql("PRAGMA table_info(customers)").allowed is False
    assert check_sql("GRANT SELECT ON customers TO public").allowed is False


def test_preserves_existing_limit():
    r = check_sql("SELECT * FROM orders LIMIT 5")
    assert r.allowed is True
    assert "LIMIT 5" in r.rewritten_sql
    assert "LIMIT 1000" not in r.rewritten_sql


def test_blocks_deep_subqueries():
    deep = "SELECT * FROM (SELECT * FROM (SELECT * FROM (SELECT * FROM (SELECT 1)))) t"
    assert check_sql(deep, GuardrailConfig(max_subquery_depth=3)).allowed is False


def test_row_limit_configurable():
    r = check_sql("SELECT * FROM orders", GuardrailConfig(default_row_limit=50))
    assert "LIMIT 50" in r.rewritten_sql
