"""DataService — Abstraction layer for Demo Mode and Company Mode.

Dashboard/analytics code calls DataService instead of raw database functions.
- Demo mode: uses .env DATABASE_URL via database/db.py
- Company mode: uses company's saved DB config via CompanyDatabase
"""
import logging
import pandas as pd
from typing import Optional

logger = logging.getLogger(__name__)


class DataService:
    """Unified data access for both Demo and Company modes."""

    def __init__(self, mode: str = "demo", company_id: str = None):
        """Initialize DataService.

        Args:
            mode: 'demo' or 'company'
            company_id: Required for company mode
        """
        self.mode = mode
        self.company_id = company_id
        self._company_db = None
        self._column_mapping = {}

    def connect(self) -> tuple[bool, str]:
        """Test the connection.

        Returns:
            (success, message)
        """
        if self.mode == "demo":
            try:
                from database.db import check_connection
                ok = check_connection()
                return ok, "Connected to demo database!" if ok else "Demo database not available"
            except Exception as e:
                return False, str(e)
        else:
            return self._connect_company()

    def _connect_company(self) -> tuple[bool, str]:
        """Connect using company's saved DB config."""
        try:
            from database.company_manager import get_db_config, get_column_mapping
            from database.company_db import CompanyDatabase

            config = get_db_config(self.company_id)
            if not config:
                return False, "No database configuration found for this company"

            db_type = config.get("db_type", "postgresql")
            self._company_db = CompanyDatabase(
                db_type=db_type,
                host=config.get("host", ""),
                port=config.get("port", 0),
                database=config.get("database", ""),
                username=config.get("username", ""),
                password=config.get("password", ""),
                sqlite_path=config.get("sqlite_path", ""),
            )

            success, msg = self._company_db.test_connection()
            if success:
                self._column_mapping = get_column_mapping(self.company_id)
            return success, msg

        except Exception as e:
            return False, f"Connection error: {str(e)}"

    def get_tables(self) -> list[str]:
        """Get available tables."""
        if self.mode == "demo":
            try:
                from database.db import get_all_tables
                return get_all_tables()
            except Exception:
                return []
        else:
            if self._company_db:
                return self._company_db.get_tables()
            return []

    def get_schema(self, table_name: str = None) -> str:
        """Get schema info (formatted for LLM)."""
        if self.mode == "demo":
            try:
                from database.db import get_table_schema
                return get_table_schema()
            except Exception:
                return ""
        else:
            if self._company_db:
                return self._company_db.get_all_schemas()
            return ""

    def get_table_columns(self, table_name: str) -> list[dict]:
        """Get columns for a specific table."""
        if self.mode == "demo":
            try:
                from database.db import get_table_columns as _get_cols
                return _get_cols(table_name)
            except Exception:
                return []
        else:
            if self._company_db:
                return self._company_db.get_table_schema(table_name)
            return []

    def execute_query(self, sql: str) -> pd.DataFrame:
        """Execute a read-only SQL query.

        Returns:
            DataFrame with results
        """
        if self.mode == "demo":
            from database.db import execute_read_query
            return execute_read_query(sql)
        else:
            if self._company_db:
                return self._company_db.execute_query(sql)
            return pd.DataFrame()

    def load_table(self, table_name: str, limit: int = 5000) -> pd.DataFrame:
        """Load data from a table."""
        if self.mode == "demo":
            from database.db import execute_read_query
            return execute_read_query(f"SELECT * FROM {table_name} LIMIT {limit}")
        else:
            if self._company_db:
                return self._company_db.read_table(table_name, limit)
            return pd.DataFrame()

    def load_mapped_data(self, table_name: str, limit: int = 5000) -> pd.DataFrame:
        """Load table data and rename columns using the company's column mapping.

        For demo mode, returns data as-is (no mapping needed).
        For company mode, renames company columns to RetailPulse standard fields.
        """
        df = self.load_table(table_name, limit)
        if df.empty or not self._column_mapping:
            return df

        # Reverse mapping: company_col -> standard_field
        reverse_map = {v: k for k, v in self._column_mapping.items() if v in df.columns}
        if reverse_map:
            df = df.rename(columns=reverse_map)

        return df
