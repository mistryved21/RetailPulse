"""Universal Multi-Database Connection Abstraction Layer for RetailPulse.

Supports:
- PostgreSQL (psycopg2)
- MySQL (pymysql)
- SQLite (sqlite3 / SQLAlchemy)
- Snowflake (snowflake-sqlalchemy)

Provides a standard DatabaseAdapter interface for connection testing,
schema/table discovery, metadata extraction, row counts, preview, and safe read-only queries.
"""
import abc
import logging
import os
import re
from typing import Any, Optional
import pandas as pd
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import OperationalError, SQLAlchemyError

logger = logging.getLogger(__name__)


class BaseDatabaseAdapter(abc.ABC):
    """Abstract base adapter for database engines."""

    def __init__(self, config: dict):
        self.config = config
        self.engine = None
        self._url = None

    @abc.abstractmethod
    def build_url(self) -> str:
        """Construct the SQLAlchemy connection URL."""
        pass

    @abc.abstractmethod
    def get_provider_name(self) -> str:
        """Return human-readable database provider name."""
        pass

    def test_connection(self) -> tuple[bool, str, dict]:
        """Test authentication and connectivity.
        
        Returns:
            (success: bool, message: str, metadata: dict)
        """
        try:
            url = self.build_url()
            eng = create_engine(
                url,
                connect_args={"connect_timeout": 8} if "sqlite" not in url else {}
            )
            with eng.connect() as conn:
                conn.execute(text("SELECT 1"))
            
            # Store working engine
            self.engine = eng
            
            # Discover basic info
            schemas = self.list_schemas()
            tables = self.list_tables()
            
            info = {
                "provider": self.get_provider_name(),
                "database": self.config.get("database") or os.path.basename(str(self.config.get("sqlite_path", "database"))),
                "schemas": schemas,
                "table_count": len(tables),
                "tables": tables
            }
            return True, f"✅ Successfully connected to {self.get_provider_name()} database '{info['database']}'!", info
        except OperationalError as e:
            msg = str(e).split("\n")[0]
            logger.warning(f"Connection test failed for {self.get_provider_name()}: {msg}")
            if "password authentication failed" in msg.lower():
                return False, "❌ Authentication failed: Incorrect username or password.", {}
            elif "could not connect to server" in msg.lower() or "connection refused" in msg.lower():
                return False, f"❌ Host unreachable: Cannot connect to {self.config.get('host')}:{self.config.get('port')}.", {}
            elif "database" in msg.lower() and "does not exist" in msg.lower():
                return False, f"❌ Database '{self.config.get('database')}' does not exist on the server.", {}
            return False, f"❌ Database connection failed: {msg}", {}
        except Exception as e:
            logger.error(f"Unexpected connection error for {self.get_provider_name()}: {e}")
            return False, f"❌ Connection error: {str(e)}", {}

    def get_engine(self):
        """Get or create the SQLAlchemy engine with pooling."""
        if self.engine is None:
            url = self.build_url()
            self.engine = create_engine(
                url,
                pool_size=5,
                max_overflow=10,
                pool_pre_ping=True,
                connect_args={"connect_timeout": 8} if "sqlite" not in url else {}
            )
        return self.engine

    def list_databases(self) -> list[str]:
        """List available databases if permitted."""
        return [self.config.get("database", "default")]

    def list_schemas(self) -> list[str]:
        """List available schemas."""
        try:
            insp = inspect(self.get_engine())
            return insp.get_schema_names() if hasattr(insp, "get_schema_names") else ["public"]
        except Exception:
            return ["public"]

    def list_tables(self, schema: str = None) -> list[str]:
        """List tables in the database/schema."""
        try:
            insp = inspect(self.get_engine())
            if schema and schema in (self.list_schemas()):
                return sorted(insp.get_table_names(schema=schema))
            return sorted(insp.get_table_names())
        except Exception as e:
            logger.error(f"Error listing tables: {e}")
            return []

    def get_table_columns(self, table_name: str, schema: str = None) -> list[dict]:
        """Get columns and data types for a table."""
        try:
            insp = inspect(self.get_engine())
            cols = insp.get_columns(table_name, schema=schema) if schema else insp.get_columns(table_name)
            return [
                {
                    "name": c["name"],
                    "type": str(c["type"]),
                    "nullable": c.get("nullable", True),
                    "primary_key": c.get("primary_key", False)
                }
                for c in cols
            ]
        except Exception as e:
            logger.error(f"Error getting columns for {table_name}: {e}")
            return []

    def get_row_count(self, table_name: str, schema: str = None) -> int:
        """Get total rows for a table safely."""
        try:
            with self.get_engine().connect() as conn:
                full_name = f'"{schema}"."{table_name}"' if schema else f'"{table_name}"'
                res = conn.execute(text(f'SELECT COUNT(*) FROM {full_name}'))
                return int(res.scalar() or 0)
        except Exception:
            return 0

    def get_tables_metadata(self, schema: str = None) -> list[dict]:
        """Get all tables with row count and column count."""
        tables = self.list_tables(schema=schema)
        meta = []
        for t in tables:
            rows = self.get_row_count(t, schema=schema)
            cols = self.get_table_columns(t, schema=schema)
            meta.append({
                "table_name": t,
                "schema": schema or "public",
                "row_count": rows,
                "column_count": len(cols),
                "columns": cols
            })
        return meta

    def preview_table(self, table_name: str, schema: str = None, limit: int = 100) -> pd.DataFrame:
        """Safely preview first N rows of a table."""
        try:
            full_name = f'"{schema}"."{table_name}"' if schema else f'"{table_name}"'
            query = f"SELECT * FROM {full_name} LIMIT {limit}"
            return pd.read_sql(query, self.get_engine())
        except Exception as e:
            logger.error(f"Error previewing table {table_name}: {e}")
            return pd.DataFrame()

    def execute_query(self, sql: str, params: dict = None) -> pd.DataFrame:
        """Execute a read-only SQL query."""
        # Block destructive SQL for external databases
        forbidden = r'\b(insert|update|delete|drop|alter|create|truncate|grant|revoke)\b'
        if re.search(forbidden, sql, re.IGNORECASE):
            raise ValueError("Only read-only SELECT queries are allowed on connected databases.")
        
        return pd.read_sql(sql, self.get_engine(), params=params)

    def close(self):
        """Dispose of the connection engine."""
        if self.engine:
            self.engine.dispose()
            self.engine = None


class PostgreSQLAdapter(BaseDatabaseAdapter):
    """PostgreSQL Adapter with explicit information_schema discovery and SSL support."""

    def get_provider_name(self) -> str:
        return "PostgreSQL"

    def build_url(self) -> str:
        host = self.config.get("host", "localhost")
        port = int(self.config.get("port") or 5432)
        database = self.config.get("database", "retailpulse_db")
        username = self.config.get("username", "retailpulse")
        password = self.config.get("password", "")
        ssl = self.config.get("ssl", False)
        
        url = f"postgresql+psycopg2://{username}:{password}@{host}:{port}/{database}"
        if ssl:
            url += "?sslmode=require"
        self._url = url
        return url

    def list_tables(self, schema: str = "public") -> list[str]:
        """Reliably discover PostgreSQL public tables using information_schema."""
        try:
            with self.get_engine().connect() as conn:
                res = conn.execute(text("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = :sch 
                      AND table_type = 'BASE TABLE'
                    ORDER BY table_name;
                """), {"sch": schema or "public"}).fetchall()
                tables = [r[0] for r in res]
                if tables:
                    return sorted(tables)
        except Exception as e:
            logger.warning(f"information_schema query failed in PostgresAdapter: {e}")
            
        return super().list_tables(schema=schema)


class MySQLAdapter(BaseDatabaseAdapter):
    """MySQL Adapter using PyMySQL."""

    def get_provider_name(self) -> str:
        return "MySQL"

    def build_url(self) -> str:
        host = self.config.get("host", "localhost")
        port = int(self.config.get("port") or 3306)
        database = self.config.get("database", "")
        username = self.config.get("username", "root")
        password = self.config.get("password", "")
        
        self._url = f"mysql+pymysql://{username}:{password}@{host}:{port}/{database}"
        return self._url

    def list_tables(self, schema: str = None) -> list[str]:
        try:
            with self.get_engine().connect() as conn:
                res = conn.execute(text("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = :db 
                      AND table_type = 'BASE TABLE'
                    ORDER BY table_name;
                """), {"db": self.config.get("database")}).fetchall()
                tables = [r[0] for r in res]
                if tables:
                    return sorted(tables)
        except Exception:
            pass
        return super().list_tables(schema=schema)


class SQLiteAdapter(BaseDatabaseAdapter):
    """SQLite file-based database adapter."""

    def get_provider_name(self) -> str:
        return "SQLite"

    def build_url(self) -> str:
        path = self.config.get("sqlite_path") or self.config.get("database") or "data/retailpulse.db"
        # Ensure path uses forward slashes for SQLAlchemy
        norm_path = os.path.normpath(path).replace("\\", "/")
        self._url = f"sqlite:///{norm_path}"
        return self._url

    def list_tables(self, schema: str = None) -> list[str]:
        try:
            with self.get_engine().connect() as conn:
                res = conn.execute(text("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name NOT LIKE 'sqlite_%'
                    ORDER BY name;
                """)).fetchall()
                return sorted([r[0] for r in res])
        except Exception:
            return super().list_tables(schema=schema)


class SnowflakeAdapter(BaseDatabaseAdapter):
    """Snowflake Cloud Data Warehouse Adapter."""

    def get_provider_name(self) -> str:
        return "Snowflake"

    def build_url(self) -> str:
        account = self.config.get("account") or self.config.get("host", "")
        user = self.config.get("username", "")
        password = self.config.get("password", "")
        database = self.config.get("database", "")
        schema = self.config.get("schema", "PUBLIC")
        warehouse = self.config.get("warehouse", "")
        role = self.config.get("role", "")
        
        url = f"snowflake://{user}:{password}@{account}/{database}/{schema}"
        params = []
        if warehouse:
            params.append(f"warehouse={warehouse}")
        if role:
            params.append(f"role={role}")
        if params:
            url += "?" + "&".join(params)
            
        self._url = url
        return url


class DatabaseConnectionManager:
    """Factory and manager for database connections and adapters."""

    @staticmethod
    def get_adapter(db_type: str, config: dict) -> BaseDatabaseAdapter:
        """Create and return the appropriate database adapter."""
        t = db_type.lower().strip()
        if t in ("postgresql", "postgres", "psql"):
            return PostgreSQLAdapter(config)
        elif t in ("mysql", "mariadb"):
            return MySQLAdapter(config)
        elif t in ("sqlite", "sqlite3"):
            return SQLiteAdapter(config)
        elif t in ("snowflake",):
            return SnowflakeAdapter(config)
        else:
            raise ValueError(f"Unsupported database provider '{db_type}'. Choose PostgreSQL, MySQL, SQLite, or Snowflake.")

    @staticmethod
    def resolve_default_host() -> str:
        """Detect if running inside Docker or on Windows Host."""
        if os.path.exists("/.dockerenv") or os.environ.get("RUNNING_IN_DOCKER"):
            return os.environ.get("DATABASE_HOST", "retailpulse_postgres")
        return os.environ.get("DATABASE_HOST", "localhost")
