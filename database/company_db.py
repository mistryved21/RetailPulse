"""External database connector for RetailPulse.

Allows companies to connect their own PostgreSQL, MySQL, SQLite, or Snowflake databases.
"""
import logging
from typing import Optional

import pandas as pd
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.exc import OperationalError
from utils.config import settings

logger = logging.getLogger(__name__)


class CompanyDatabase:
    """Manage external company database connections."""

    def __init__(self, db_type: str, host: str = "", port: int | str = 0,
                 database: str = "", username: str = "", password: str = "",
                 sqlite_path: str = ""):
        """Initialize company database connection.

        Args:
            db_type: 'postgresql', 'mysql', 'sqlite', or 'snowflake'
            host: Database host
            port: Database port (int or str)
            database: Database name
            username: Database username
            password: Database password
            sqlite_path: Path to SQLite file (only for sqlite)
        """
        self.db_type = db_type.lower()
        self.host = host
        try:
            self.port = int(port) if port else 0
        except Exception:
            self.port = 0
            
        self.database = database
        self.username = username
        self.password = password
        self.sqlite_path = sqlite_path
        self.engine = None
        self._build_url()

    def _build_url(self):
        """Build SQLAlchemy connection URL."""
        if self.db_type == "postgresql":
            self.port = self.port or 5432
            self.url = f"postgresql+psycopg2://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"
        elif self.db_type == "mysql":
            self.port = self.port or 3306
            self.url = f"mysql+pymysql://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"
        elif self.db_type == "sqlite":
            self.url = f"sqlite:///{self.sqlite_path}"
        elif self.db_type == "snowflake":
            self.url = f"snowflake://{self.username}:{self.password}@{self.host}/{self.database}"
        else:
            raise ValueError(f"Unsupported database type: {self.db_type}. Use postgresql/mysql/sqlite/snowflake")

    def test_connection(self) -> tuple[bool, str]:
        """Test the database connection.

        Returns:
            tuple of (success, message)
        """
        try:
            engine = create_engine(
                self.url,
                connect_args={"connect_timeout": 10} if self.db_type != "sqlite" else {}
            )
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            
            # Keep engine active on success
            self.engine = engine
            logger.info(f"Connection test passed: {self.db_type}://{self.host}/{self.database}")
            return True, "Successfully connected to database!"
        except OperationalError as e:
            msg = str(e).split("\n")[0]
            logger.error(f"Connection test failed: {msg}")
            return False, f"Connection failed: {msg}"
        except Exception as e:
            logger.error(f"Connection error: {e}")
            return False, f"Error: {str(e)}"

    def connect(self) -> bool:
        """Establish the database connection.

        Returns:
            True if connected successfully
        """
        if self.engine:
            return True
        try:
            self.engine = create_engine(
                self.url,
                pool_size=3,
                max_overflow=5,
                pool_pre_ping=True,
                connect_args={"connect_timeout": 10} if self.db_type != "sqlite" else {}
            )
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info(f"Connected to {self.db_type}://{self.host}/{self.database}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            self.engine = None
            return False

    def get_tables(self) -> list[str]:
        """Get list of all tables in the database with reliable schema queries.

        Returns:
            List of table names
        """
        if not self.engine:
            if not self.connect():
                return []
        try:
            # First try direct SQL for PostgreSQL
            if self.db_type in ("postgresql", "snowflake"):
                with self.engine.connect() as conn:
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
            elif self.db_type == "mysql":
                with self.engine.connect() as conn:
                    res = conn.execute(text("""
                        SELECT table_name 
                        FROM information_schema.tables 
                        WHERE table_schema = :db_name 
                          AND table_type = 'BASE TABLE'
                        ORDER BY table_name;
                    """), {"db_name": self.database}).fetchall()
                    tables = [r[0] for r in res]
                    if tables:
                        return sorted(tables)

            # Fallback to inspector
            inspector = inspect(self.engine)
            tables = inspector.get_table_names(schema="public") if "public" in (inspector.get_schema_names() if hasattr(inspector, "get_schema_names") else []) else inspector.get_table_names()
            logger.info(f"Found {len(tables)} tables: {tables}")
            return sorted(tables)
        except Exception as e:
            logger.error(f"Failed to get tables: {e}")
            return []

    def get_tables_with_counts(self) -> list[dict]:
        """Get tables along with row count and column count.
        
        Returns:
            list of dict: [{"table_name": str, "row_count": int, "column_count": int}]
        """
        tables = self.get_tables()
        if not tables or not self.engine:
            return []
            
        res = []
        for t in tables:
            try:
                with self.engine.connect() as conn:
                    cnt = conn.execute(text(f'SELECT COUNT(*) FROM "{t}"')).scalar() or 0
                    inspector = inspect(self.engine)
                    cols = inspector.get_columns(t)
                    res.append({
                        "table_name": t,
                        "row_count": int(cnt),
                        "column_count": len(cols)
                    })
            except Exception:
                res.append({
                    "table_name": t,
                    "row_count": 0,
                    "column_count": 0
                })
        return res

    def get_table_schema(self, table_name: str) -> list[dict]:
        """Get schema of a specific table.

        Args:
            table_name: Name of the table

        Returns:
            List of dicts with column info
        """
        if not self.engine:
            if not self.connect():
                return []
        try:
            inspector = inspect(self.engine)
            columns = inspector.get_columns(table_name)
            return [{"name": c["name"], "type": str(c["type"]), "nullable": c.get("nullable", True)}
                    for c in columns]
        except Exception as e:
            logger.error(f"Failed to get schema for {table_name}: {e}")
            return []

    def get_all_schemas(self) -> str:
        """Get all table schemas as a formatted string (for LLM context).

        Returns:
            String with all table schemas
        """
        tables = self.get_tables()
        if not tables:
            return "No tables found"

        schema_str = ""
        for table in tables:
            columns = self.get_table_schema(table)
            cols = ", ".join([f"{c['name']} ({c['type']})" for c in columns])
            schema_str += f"TABLE {table}: {cols}\n"
        return schema_str

    def read_table(self, table_name: str, limit: int = 10000) -> pd.DataFrame:
        """Read data from a table.

        Args:
            table_name: Name of the table
            limit: Maximum rows to read

        Returns:
            DataFrame with table data
        """
        if not self.engine:
            if not self.connect():
                return pd.DataFrame()
        try:
            query = f'SELECT * FROM "{table_name}" LIMIT {limit}'
            df = pd.read_sql(query, self.engine)
            logger.info(f"Read {len(df)} rows from {table_name}")
            return df
        except Exception as e:
            logger.error(f"Failed to read {table_name}: {e}")
            return pd.DataFrame()

    def execute_query(self, sql: str) -> pd.DataFrame:
        """Execute a read-only SQL query.

        Args:
            sql: SQL SELECT query

        Returns:
            DataFrame with results

        Raises:
            ValueError: If query is not SELECT/WITH
        """
        # Safety check
        upper = sql.upper().strip()
        dangerous = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "TRUNCATE"]
        for keyword in dangerous:
            if keyword in upper.split():
                raise ValueError(f"Dangerous SQL keyword detected: {keyword}. Only SELECT allowed.")

        if not self.engine:
            if not self.connect():
                raise ConnectionError("Database not connected")
        try:
            df = pd.read_sql(sql, self.engine)
            logger.info(f"Query executed: {len(df)} rows returned")
            return df
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            raise

    def disconnect(self):
        """Close the database connection."""
        if self.engine:
            self.engine.dispose()
            self.engine = None
            logger.info("Database disconnected")


def import_dataframe_to_db(df: pd.DataFrame, table_name: str, db_url: str = None) -> bool:
    """Import a DataFrame into a PostgreSQL table.

    Used to store custom uploaded file data into the RetailPulse database.

    Args:
        df: DataFrame to import
        table_name: Target table name (will be created)
        db_url: Database connection URL (defaults to settings.DATABASE_URL)

    Returns:
        True if successful
    """
    try:
        url = db_url or settings.DATABASE_URL
        engine = create_engine(url)
        clean_name = "uploaded_" + "".join(c if c.isalnum() or c == "_" else "_" for c in table_name.lower())
        df.to_sql(clean_name, engine, if_exists="replace", index=False)
        engine.dispose()
        logger.info(f"Imported {len(df)} rows into table '{clean_name}'")
        return True
    except Exception as e:
        logger.error(f"Import failed: {e}")
        return False
