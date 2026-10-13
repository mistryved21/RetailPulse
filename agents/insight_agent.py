import json
import logging
import pandas as pd
from tools.llm_wrapper import invoke_llm
from prompts.insight_prompt import INSIGHT_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

def generate_insights(df: pd.DataFrame, user_query: str, context: str = '') -> dict:
    """Generate business insights from DataFrame."""
    if df.empty:
        return {
            'summary': 'No data available.',
            'key_findings': [],
            'recommendations': [],
            'risk_alerts': []
        }
    
    stats = df.describe().to_string()
    head = df.head().to_string()
    value_counts = df.apply(pd.Series.value_counts).to_string() if len(df.columns) > 0 else ""
    
    prompt = f"Query: {user_query}\nContext: {context}\nStats:\n{stats}\nHead:\n{head}\nValue Counts:\n{value_counts}\n\nReturn JSON with keys: summary, key_findings (list), recommendations (list), risk_alerts (list)."
    
    try:
        response = invoke_llm(prompt, system_prompt=INSIGHT_SYSTEM_PROMPT)
        clean = response.strip()
        if '```json' in clean:
            clean = clean.split('```json')[1].split('```')[0]
        elif '```' in clean:
            clean = clean.split('```')[1].split('```')[0]
        
        parsed = json.loads(clean.strip())
        return {
            'summary': parsed.get('summary', ''),
            'key_findings': parsed.get('key_findings', []),
            'recommendations': parsed.get('recommendations', []),
            'risk_alerts': parsed.get('risk_alerts', [])
        }
    except Exception as e:
        logger.error(f"Insight generation failed: {e}")
        return {
            'summary': 'Could not generate insights due to an error.',
            'key_findings': [],
            'recommendations': [],
            'risk_alerts': []
        }
