import re
import logging
import pandas as pd
from tools.llm_wrapper import invoke_llm
from prompts.sql_prompt import SQL_SYSTEM_PROMPT, SQL_USER_PROMPT_TEMPLATE
from database.db import execute_read_query, get_table_schema

logger = logging.getLogger(__name__)

DANGEROUS_KEYWORDS = [
    'INSERT', 'UPDATE', 'DELETE', 'DROP', 'ALTER',
    'CREATE', 'TRUNCATE', 'EXECUTE', 'GRANT', 'REVOKE'
]

def validate_sql(sql: str) -> bool:
    """Validate that SQL is read-only (SELECT only)."""
    upper = sql.upper().strip()
    for keyword in DANGEROUS_KEYWORDS:
        pattern = r'\b' + keyword + r'\b'
        if re.search(pattern, upper):
            logger.warning(f"Dangerous SQL keyword detected: {keyword}")
            return False
    if not upper.startswith('SELECT') and not upper.startswith('WITH'):
        logger.warning(f"SQL does not start with SELECT or WITH")
        return False
    return True

def generate_sql(user_query: str) -> str:
    """Generate PostgreSQL SELECT query from natural language."""
    schema = get_table_schema()
    prompt = SQL_USER_PROMPT_TEMPLATE.format(schema=schema, question=user_query)
    response = invoke_llm(prompt, system_prompt=SQL_SYSTEM_PROMPT)
    
    # Extract SQL from response
    sql = response.strip()
    if '```sql' in sql:
        sql = sql.split('```sql')[1].split('```')[0]
    elif '```' in sql:
        sql = sql.split('```')[1].split('```')[0]
    sql = sql.strip().rstrip(';') + ';'
    
    logger.info(f"Generated SQL: {sql}")
    return sql

def run_sql_agent(user_query: str) -> tuple[str, pd.DataFrame]:
    """Full SQL agent pipeline: generate SQL -> validate -> execute.
    
    Returns:
        tuple of (sql_query, result_dataframe)
    """
    try:
        sql = generate_sql(user_query)
        if not validate_sql(sql):
            raise ValueError("Generated SQL contains dangerous operations. Only SELECT queries are allowed.")
        df = execute_read_query(sql)
        logger.info(f"SQL executed successfully. Rows: {len(df)}, Columns: {list(df.columns)}")
        return sql, df
    except Exception as e:
        logger.error(f"SQL Agent failed: {e}")
        raise
