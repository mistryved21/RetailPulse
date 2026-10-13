"""Tests for SQL Agent."""
from agents.sql_agent import validate_sql

def test_validate_select():
    assert validate_sql('SELECT * FROM products') == True

def test_validate_with_cte():
    assert validate_sql('WITH cte AS (SELECT 1) SELECT * FROM cte') == True

def test_block_delete():
    assert validate_sql('DELETE FROM products') == False

def test_block_drop():
    assert validate_sql('DROP TABLE products') == False

def test_block_insert():
    assert validate_sql('INSERT INTO products VALUES (1)') == False

def test_block_update():
    assert validate_sql('UPDATE products SET price = 0') == False
