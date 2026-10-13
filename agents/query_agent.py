import logging
from tools.llm_wrapper import invoke_llm

logger = logging.getLogger(__name__)

def parse_query(user_query: str) -> dict:
    """Parse and understand the user's natural language query.
    
    Returns:
        dict with 'original_query', 'parsed_intent', 'entities', 'time_period'
    """
    system_prompt = """You are a retail analytics query parser. Analyze the user's question and extract:
1. intent: what they want to know (sales_analysis, inventory_check, customer_analysis, product_analysis, forecast, comparison, report)
2. entities: products, categories, regions, customers mentioned
3. time_period: any date range mentioned (e.g., 'March 2024', 'last quarter', '2024 vs 2025')
4. metrics: what metrics they care about (revenue, quantity, profit, stock_level, etc.)

Respond in JSON format:
{"intent": "...", "entities": [...], "time_period": "...", "metrics": [...]}"""
    
    try:
        response = invoke_llm(user_query, system_prompt=system_prompt)
        import json
        clean = response.strip()
        if '```json' in clean:
            clean = clean.split('```json')[1].split('```')[0]
        elif '```' in clean:
            clean = clean.split('```')[1].split('```')[0]
        parsed = json.loads(clean.strip())
        result = {
            'original_query': user_query,
            'parsed_intent': parsed.get('intent', 'general'),
            'entities': parsed.get('entities', []),
            'time_period': parsed.get('time_period', ''),
            'metrics': parsed.get('metrics', ['revenue'])
        }
        logger.info(f"Parsed query: {result['parsed_intent']}")
        return result
    except Exception as e:
        logger.error(f"Query parsing failed: {e}")
        return {
            'original_query': user_query,
            'parsed_intent': 'general',
            'entities': [],
            'time_period': '',
            'metrics': ['revenue']
        }
