"""LangGraph workflow orchestrating all RetailPulse agents."""
import logging
from typing import TypedDict, Optional, Any
import pandas as pd
from langgraph.graph import StateGraph, END

from agents.planner_agent import plan_query
from agents.query_agent import parse_query
from agents.sql_agent import run_sql_agent
from agents.visualization_agent import create_visualization, save_chart
from agents.forecast_agent import run_forecast
from agents.insight_agent import generate_insights
from agents.pdf_agent import generate_report
from agents.email_agent import send_email

logger = logging.getLogger(__name__)


class AgentState(TypedDict):
    """State passed between agents in the workflow."""
    user_query: str
    plan: dict
    parsed_query: dict
    sql_query: str
    data: Any  # pd.DataFrame
    chart_figure: Any  # plotly Figure
    chart_path: str
    forecast_result: dict
    insights: dict
    pdf_path: str
    email_sent: bool
    email_to: str
    error: str
    status: str


# ── Node Functions ────────────────────────────────────────────

def planning_node(state: AgentState) -> AgentState:
    """Plan which agents are needed for this query."""
    try:
        plan = plan_query(state['user_query'])
        return {**state, 'plan': plan, 'status': 'planned'}
    except Exception as e:
        logger.error(f"Planning failed: {e}")
        return {**state, 'plan': {'needs_sql': True, 'needs_visualization': True, 'needs_insight': True}, 'status': 'planned'}


def query_parsing_node(state: AgentState) -> AgentState:
    """Parse the natural language query."""
    parsed = parse_query(state['user_query'])
    return {**state, 'parsed_query': parsed}


def sql_node(state: AgentState) -> AgentState:
    """Generate and execute SQL query."""
    try:
        sql, df = run_sql_agent(state['user_query'])
        return {**state, 'sql_query': sql, 'data': df, 'status': 'data_ready'}
    except Exception as e:
        logger.error(f"SQL node failed: {e}")
        return {**state, 'error': str(e), 'status': 'error'}


def visualization_node(state: AgentState) -> AgentState:
    """Create visualization from data."""
    try:
        if state.get('data') is None or (isinstance(state['data'], pd.DataFrame) and state['data'].empty):
            return state
        chart_type = state.get('plan', {}).get('chart_type', 'auto')
        fig = create_visualization(state['data'], state['user_query'], chart_type=chart_type)
        chart_path = save_chart(fig, 'chart')
        return {**state, 'chart_figure': fig, 'chart_path': chart_path, 'status': 'visualized'}
    except Exception as e:
        logger.error(f"Visualization failed: {e}")
        return state


def forecast_node(state: AgentState) -> AgentState:
    """Run forecasting models."""
    try:
        if state.get('data') is None or (isinstance(state['data'], pd.DataFrame) and state['data'].empty):
            return state
        result = run_forecast(state['data'])
        return {**state, 'forecast_result': result, 'status': 'forecasted'}
    except Exception as e:
        logger.error(f"Forecast failed: {e}")
        return state


def insight_node(state: AgentState) -> AgentState:
    """Generate business insights."""
    try:
        if state.get('data') is None or (isinstance(state['data'], pd.DataFrame) and state['data'].empty):
            return {**state, 'insights': {'summary': 'No data available for analysis.', 'key_findings': [], 'recommendations': [], 'risk_alerts': []}}
        insights = generate_insights(state['data'], state['user_query'])
        return {**state, 'insights': insights, 'status': 'insights_ready'}
    except Exception as e:
        logger.error(f"Insight generation failed: {e}")
        return {**state, 'insights': {'summary': f'Insight generation failed: {e}', 'key_findings': [], 'recommendations': [], 'risk_alerts': []}}


def pdf_node(state: AgentState) -> AgentState:
    """Generate PDF report."""
    try:
        chart_paths = [state.get('chart_path', '')] if state.get('chart_path') else []
        pdf_path = generate_report(
            title=f"RetailPulse Report: {state['user_query'][:50]}",
            summary=state.get('insights', {}).get('summary', ''),
            df=state.get('data'),
            chart_paths=chart_paths,
            insights=state.get('insights', {}),
        )
        return {**state, 'pdf_path': pdf_path, 'status': 'report_ready'}
    except Exception as e:
        logger.error(f"PDF generation failed: {e}")
        return state


def email_node(state: AgentState) -> AgentState:
    """Send report via email."""
    try:
        email_to = state.get('email_to', '')
        if not email_to:
            return {**state, 'email_sent': False}
        success = send_email(
            to_email=email_to,
            subject=f"RetailPulse Report: {state['user_query'][:50]}",
            body=state.get('insights', {}).get('summary', 'Please find your report attached.'),
            attachment_path=state.get('pdf_path', '')
        )
        return {**state, 'email_sent': success, 'status': 'email_sent' if success else 'email_failed'}
    except Exception as e:
        logger.error(f"Email failed: {e}")
        return {**state, 'email_sent': False}


# ── Conditional Routing ───────────────────────────────────────

def should_forecast(state: AgentState) -> str:
    if state.get('plan', {}).get('needs_forecast', False):
        return 'forecast'
    return 'insight'

def should_email(state: AgentState) -> str:
    if state.get('plan', {}).get('needs_report', False) or state.get('plan', {}).get('needs_email', False):
        return 'pdf'
    return 'end'

def should_send_email(state: AgentState) -> str:
    if state.get('email_to') and state.get('pdf_path'):
        return 'email'
    return 'end'


# ── Build the Graph ───────────────────────────────────────────

def build_workflow() -> StateGraph:
    """Build and compile the LangGraph workflow."""
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node('planner', planning_node)
    workflow.add_node('query_parser', query_parsing_node)
    workflow.add_node('sql', sql_node)
    workflow.add_node('visualization', visualization_node)
    workflow.add_node('forecast', forecast_node)
    workflow.add_node('insight', insight_node)
    workflow.add_node('pdf', pdf_node)
    workflow.add_node('email', email_node)
    
    # Define edges
    workflow.set_entry_point('planner')
    workflow.add_edge('planner', 'query_parser')
    workflow.add_edge('query_parser', 'sql')
    workflow.add_edge('sql', 'visualization')
    workflow.add_conditional_edges('visualization', should_forecast, {'forecast': 'forecast', 'insight': 'insight'})
    workflow.add_edge('forecast', 'insight')
    workflow.add_conditional_edges('insight', should_email, {'pdf': 'pdf', 'end': END})
    workflow.add_conditional_edges('pdf', should_send_email, {'email': 'email', 'end': END})
    workflow.add_edge('email', END)
    
    return workflow.compile()


# ── Main entry point ──────────────────────────────────────────

def run_pipeline(user_query: str, email_to: str = '') -> dict:
    """Run the complete RetailPulse agentic pipeline.
    
    Args:
        user_query: Natural language question
        email_to: Optional email address to send report
    
    Returns:
        Final agent state with all results
    """
    logger.info(f"Starting pipeline for: {user_query}")
    
    initial_state: AgentState = {
        'user_query': user_query,
        'plan': {},
        'parsed_query': {},
        'sql_query': '',
        'data': None,
        'chart_figure': None,
        'chart_path': '',
        'forecast_result': {},
        'insights': {},
        'pdf_path': '',
        'email_sent': False,
        'email_to': email_to,
        'error': '',
        'status': 'started'
    }
    
    app = build_workflow()
    result = app.invoke(initial_state)
    
    logger.info(f"Pipeline complete. Status: {result.get('status')}")
    return result
