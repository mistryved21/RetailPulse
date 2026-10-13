import json
import logging
from tools.llm_wrapper import invoke_llm
from prompts.planner_prompt import PLANNER_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

def plan_query(user_query: str) -> dict:
    """Analyze user query and create execution plan.
    
    Returns dict with:
        needs_sql: bool
        needs_visualization: bool  
        needs_forecast: bool
        needs_insight: bool
        needs_report: bool
        needs_email: bool
        chart_type: str (bar/pie/line/area/scatter/histogram/heatmap/auto)
        description: str
    """
    try:
        response = invoke_llm(user_query, system_prompt=PLANNER_SYSTEM_PROMPT)
        # Parse JSON from response
        # Handle markdown code blocks
        clean = response.strip()
        if '```json' in clean:
            clean = clean.split('```json')[1].split('```')[0]
        elif '```' in clean:
            clean = clean.split('```')[1].split('```')[0]
        plan = json.loads(clean.strip())
        # Set defaults for missing fields
        defaults = {
            'needs_sql': True, 'needs_visualization': True,
            'needs_forecast': False, 'needs_insight': True,
            'needs_report': False, 'needs_email': False,
            'chart_type': 'auto', 'description': user_query
        }
        for k, v in defaults.items():
            plan.setdefault(k, v)
        logger.info(f"Plan created: {plan}")
        return plan
    except Exception as e:
        logger.error(f"Planning failed: {e}, using defaults")
        return {
            'needs_sql': True, 'needs_visualization': True,
            'needs_forecast': False, 'needs_insight': True,
            'needs_report': False, 'needs_email': False,
            'chart_type': 'auto', 'description': user_query
        }
