import logging
import pandas as pd
import plotly.graph_objects as go
import numpy as np

logger = logging.getLogger(__name__)

def run_forecast(df: pd.DataFrame, date_col: str, value_col: str, periods: int = 30) -> dict:
    """Run forecast using Prophet or LSTM."""
    if len(df) < 10:
        return {'error': 'Not enough data points. Need at least 10.', 'forecast_df': None, 'figure': None, 'model_used': None, 'metrics': None}
    
    try:
        from forecasting.prophet_model import run_prophet
        forecast_df, metrics = run_prophet(df, date_col, value_col, periods)
        model_used = 'Prophet'
    except Exception as e:
        logger.warning(f"Prophet failed: {e}. Falling back to SMA.")
        try:
            from forecasting.lstm_model import run_lstm
            forecast_df, metrics = run_lstm(df, date_col, value_col, periods)
            model_used = 'LSTM'
        except Exception as e2:
            logger.warning(f"LSTM failed: {e2}. Falling back to SMA.")
            # Simple Moving Average fallback
            last_val = df[value_col].iloc[-1]
            future_dates = pd.date_range(start=df[date_col].iloc[-1], periods=periods+1)[1:]
            forecast_df = pd.DataFrame({
                'ds': future_dates,
                'yhat': [last_val] * periods,
                'yhat_lower': [last_val * 0.9] * periods,
                'yhat_upper': [last_val * 1.1] * periods
            })
            metrics = {'MAE': 0, 'RMSE': 0}
            model_used = 'SMA'

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df[date_col], y=df[value_col], mode='lines', name='Actual'))
    if forecast_df is not None and 'ds' in forecast_df.columns:
        fig.add_trace(go.Scatter(x=forecast_df['ds'], y=forecast_df['yhat'], mode='lines', name='Forecast'))
        if 'yhat_upper' in forecast_df.columns and 'yhat_lower' in forecast_df.columns:
            fig.add_trace(go.Scatter(x=forecast_df['ds'], y=forecast_df['yhat_upper'], mode='lines', line=dict(width=0), showlegend=False))
            fig.add_trace(go.Scatter(x=forecast_df['ds'], y=forecast_df['yhat_lower'], mode='lines', line=dict(width=0), fillcolor='rgba(68, 68, 68, 0.3)', fill='tonexty', showlegend=False))
    
    fig.update_layout(title=f'Forecast ({model_used})', template='plotly_dark')
    
    return {
        'forecast_df': forecast_df,
        'figure': fig,
        'model_used': model_used,
        'metrics': metrics
    }
