"""Prophet-based time series forecasting."""
import logging
import pandas as pd
import numpy as np
from typing import Optional

logger = logging.getLogger(__name__)

def forecast_with_prophet(
    df: pd.DataFrame,
    date_col: str = 'date',
    value_col: str = 'value',
    periods: int = 30
) -> dict:
    """Generate forecast using Facebook Prophet.
    
    Args:
        df: DataFrame with date and value columns
        date_col: Name of the date column
        value_col: Name of the value column  
        periods: Number of future periods to forecast
    
    Returns:
        dict with 'forecast_df', 'model', 'metrics'
    """
    try:
        from prophet import Prophet
        
        # Prepare data for Prophet (requires 'ds' and 'y' columns)
        prophet_df = df[[date_col, value_col]].copy()
        prophet_df.columns = ['ds', 'y']
        prophet_df['ds'] = pd.to_datetime(prophet_df['ds'])
        prophet_df = prophet_df.dropna().sort_values('ds')
        
        if len(prophet_df) < 10:
            raise ValueError(f"Need at least 10 data points, got {len(prophet_df)}")
        
        # Fit model
        model = Prophet(
            yearly_seasonality=True,
            weekly_seasonality=True if len(prophet_df) > 14 else False,
            daily_seasonality=False,
            changepoint_prior_scale=0.05
        )
        model.fit(prophet_df)
        
        # Make future predictions
        future = model.make_future_dataframe(periods=periods)
        forecast = model.predict(future)
        
        # Calculate metrics on training data
        train_pred = forecast[forecast['ds'].isin(prophet_df['ds'])]
        merged = prophet_df.merge(train_pred[['ds', 'yhat']], on='ds')
        mae = np.mean(np.abs(merged['y'] - merged['yhat']))
        rmse = np.sqrt(np.mean((merged['y'] - merged['yhat'])**2))
        
        result_df = forecast[['ds', 'yhat', 'yhat_lower', 'yhat_upper']].copy()
        result_df.columns = ['date', 'predicted', 'lower_bound', 'upper_bound']
        
        logger.info(f"Prophet forecast done. MAE: {mae:.2f}, RMSE: {rmse:.2f}")
        return {
            'forecast_df': result_df,
            'model': 'Prophet',
            'metrics': {'mae': round(mae, 2), 'rmse': round(rmse, 2)},
            'success': True
        }
    except Exception as e:
        logger.error(f"Prophet forecasting failed: {e}")
        return {'forecast_df': pd.DataFrame(), 'model': 'Prophet', 'metrics': {}, 'success': False, 'error': str(e)}
