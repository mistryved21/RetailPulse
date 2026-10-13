import os
import logging
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from tools.llm_wrapper import invoke_llm

logger = logging.getLogger(__name__)

def create_visualization(df: pd.DataFrame, user_query: str, chart_type: str = 'auto') -> go.Figure:
    """Create a Plotly chart from a DataFrame."""
    if df.empty:
        raise ValueError("DataFrame is empty, cannot create visualization.")

    if chart_type == 'auto':
        system_prompt = "You are a data visualization expert. Respond ONLY with one of: bar, pie, line, area, scatter, histogram, heatmap. Base your choice on this user query: " + user_query
        response = invoke_llm(f"Data columns: {list(df.columns)}. Rows: {len(df)}. Query: {user_query}", system_prompt=system_prompt)
        chart_type = response.strip().lower()
        if chart_type not in ['bar', 'pie', 'line', 'area', 'scatter', 'histogram', 'heatmap']:
            chart_type = 'bar'
    
    logger.info(f"Creating {chart_type} chart.")
    
    # Simple heuristic to pick x and y
    cols = list(df.columns)
    if len(cols) >= 2:
        x_col = cols[0]
        y_col = cols[1]
    else:
        x_col = cols[0]
        y_col = cols[0]
    
    if chart_type == 'bar':
        fig = px.bar(df, x=x_col, y=y_col, title=user_query, template='plotly_dark')
    elif chart_type == 'pie':
        fig = px.pie(df, names=x_col, values=y_col, title=user_query, template='plotly_dark')
    elif chart_type == 'line':
        fig = px.line(df, x=x_col, y=y_col, title=user_query, template='plotly_dark')
    elif chart_type == 'area':
        fig = px.area(df, x=x_col, y=y_col, title=user_query, template='plotly_dark')
    elif chart_type == 'scatter':
        fig = px.scatter(df, x=x_col, y=y_col, title=user_query, template='plotly_dark')
    elif chart_type == 'histogram':
        fig = px.histogram(df, x=x_col, title=user_query, template='plotly_dark')
    elif chart_type == 'heatmap':
        if len(cols) >= 3:
            fig = px.density_heatmap(df, x=x_col, y=y_col, z=cols[2], title=user_query, template='plotly_dark')
        else:
            fig = px.density_heatmap(df, x=x_col, y=y_col, title=user_query, template='plotly_dark')
    else:
        fig = px.bar(df, x=x_col, y=y_col, title=user_query, template='plotly_dark')
        
    fig.update_layout(
        plot_bgcolor='rgba(17, 17, 17, 1)',
        paper_bgcolor='rgba(17, 17, 17, 1)',
        font_color='white'
    )
    return fig

def save_chart(fig: go.Figure, filename: str) -> str:
    """Save chart to reports/ directory."""
    reports_dir = os.path.join(os.getcwd(), 'reports')
    os.makedirs(reports_dir, exist_ok=True)
    filepath = os.path.join(reports_dir, filename)
    fig.write_image(filepath)
    return filepath
