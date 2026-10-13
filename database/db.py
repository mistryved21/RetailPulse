"""Database module for RetailPulse — fully flexible schema, lazy connection."""
import time
import re
import os
import pandas as pd
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError

from utils.config import settings
from utils.logger import get_logger

logger = get_logger(__name__)

# ── Lazy Engine (never blocks on import) ──────────────────────────────────────
_engine = None

def _get_engine():
    """Get or create the database engine lazily with a 5s timeout."""
    global _engine
    if _engine is None:
        _engine = create_engine(
            settings.DATABASE_URL,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
            connect_args={"connect_timeout": 5},
        )
    return _engine


def get_db():
    """FastAPI dependency for database session."""
    Session = sessionmaker(autocommit=False, autoflush=False, bind=_get_engine())
    db = Session()
    try:
        yield db
    finally:
        db.close()


# ── Read Queries ──────────────────────────────────────────────────────────────

def execute_read_query(sql: str, params: dict = None) -> pd.DataFrame:
    """Execute read-only SQL, returns DataFrame.

    Safety: Blocks INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, TRUNCATE.
    """
    forbidden_keywords = r'\b(insert|update|delete|drop|alter|create|truncate|execute)\b'
    if re.search(forbidden_keywords, sql, re.IGNORECASE):
        logger.error(f"Blocked forbidden SQL query: {sql}")
        raise ValueError("Only read-only queries (SELECT) are allowed.")

    start_time = time.time()
    try:
        df = pd.read_sql(sql, _get_engine(), params=params)
        duration = time.time() - start_time
        logger.info(f"Executed query in {duration:.3f}s. Rows: {len(df)}")
        return df
    except SQLAlchemyError as e:
        logger.error(f"Database error executing query: {str(e)}")
        raise


# ── Schema Discovery ─────────────────────────────────────────────────────────

def get_all_tables() -> list[str]:
    """Get list of all table names in the database using reliable PostgreSQL query."""
    try:
        eng = _get_engine()
        with eng.connect() as conn:
            # First try direct information_schema query
            res = conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                  AND table_type = 'BASE TABLE'
                ORDER BY table_name;
            """)).fetchall()
            tables = [r[0] for r in res]
            if tables:
                return sorted(tables)
        
        # Fallback to inspect
        insp = inspect(eng)
        return sorted(insp.get_table_names(schema="public") or insp.get_table_names())
    except Exception as e:
        logger.error(f"Error listing tables: {e}")
        return []


def get_tables_with_metadata() -> list[dict]:
    """Get all tables along with row count and column count.
    
    Returns:
        list of dict: [{"table_name": str, "row_count": int, "column_count": int}]
    """
    tables = get_all_tables()
    meta = []
    eng = _get_engine()
    
    for t in tables:
        try:
            with eng.connect() as conn:
                r_count = conn.execute(text(f'SELECT COUNT(*) FROM "{t}"')).scalar() or 0
                c_count = conn.execute(text(f"""
                    SELECT COUNT(*) 
                    FROM information_schema.columns 
                    WHERE table_schema = 'public' AND table_name = :t_name
                """), {"t_name": t}).scalar() or 0
                meta.append({
                    "table_name": t,
                    "row_count": int(r_count),
                    "column_count": int(c_count)
                })
        except Exception as err:
            logger.warning(f"Error reading metadata for table {t}: {err}")
            meta.append({
                "table_name": t,
                "row_count": 0,
                "column_count": 0
            })
            
    return meta


def get_table_schema() -> str:
    """Dynamically reads ALL tables and columns from the live database."""
    try:
        eng = _get_engine()
        insp = inspect(eng)
        schema_parts = []
        tables = get_all_tables()

        for table_name in tables:
            columns = insp.get_columns(table_name, schema="public") if "public" in insp.get_schema_names() else insp.get_columns(table_name)
            col_strs = []
            for col in columns:
                col_str = f"{col['name']} ({col['type']})"
                if col.get("primary_key"):
                    col_str += " PK"
                if col.get("nullable") is False:
                    col_str += " NOT NULL"
                col_strs.append(col_str)

            # Foreign keys
            try:
                fks = insp.get_foreign_keys(table_name, schema="public")
            except Exception:
                fks = []
                
            fk_strs = []
            for fk in fks:
                for col in fk.get("constrained_columns", []):
                    ref = f"{fk['referred_table']}.{fk['referred_columns'][0]}" if fk.get("referred_columns") else fk["referred_table"]
                    fk_strs.append(f"{col} -> {ref}")

            # Row count
            try:
                with eng.connect() as conn:
                    result = conn.execute(text(f'SELECT COUNT(*) FROM "{table_name}"'))
                    row_count = result.scalar() or 0
            except Exception:
                row_count = "?"

            part = f"TABLE: {table_name} ({row_count} rows)\n"
            part += f"  COLUMNS: {', '.join(col_strs)}"
            if fk_strs:
                part += f"\n  FOREIGN KEYS: {', '.join(fk_strs)}"
            schema_parts.append(part)

        schema = "\n\n".join(schema_parts)
        logger.info(f"Schema discovered: {len(schema_parts)} tables")
        return schema
    except Exception as e:
        logger.error(f"Error getting table schema: {e}")
        return ""


def get_table_columns(table_name: str) -> list[dict]:
    """Get columns of a specific table."""
    try:
        eng = _get_engine()
        insp = inspect(eng)
        columns = insp.get_columns(table_name, schema="public") if "public" in insp.get_schema_names() else insp.get_columns(table_name)
        return [{"name": c["name"], "type": str(c["type"]), "nullable": c.get("nullable", True)}
                for c in columns]
    except Exception as e:
        logger.error(f"Error getting columns for {table_name}: {e}")
        return []


def get_table_sample(table_name: str, limit: int = 5) -> pd.DataFrame:
    """Get a sample of rows from a table."""
    try:
        return pd.read_sql(f'SELECT * FROM "{table_name}" LIMIT {limit}', _get_engine())
    except Exception:
        return pd.DataFrame()


def check_connection() -> bool:
    """Tests DB connectivity (5-second timeout, never hangs)."""
    try:
        with _get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"Connection test failed: {e}")
        return False
