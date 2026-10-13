"""Ensemble forecasting combining Prophet and LSTM."""
import logging
import pandas as pd
import numpy as np
from forecasting.prophet_model import forecast_with_prophet
from forecasting.lstm_model import forecast_with_lstm

logger = logging.getLogger(__name__)

def forecast_ensemble(
    df: pd.DataFrame,
    date_col: str = 'date',
    value_col: str = 'value',
    periods: int = 30
) -> dict:
    """Generate ensemble forecast combining Prophet and LSTM.
    
    Uses weighted average based on training metrics.
    Falls back to whichever model succeeds if one fails.
    """
    prophet_result = forecast_with_prophet(df, date_col, value_col, periods)
    lstm_result = forecast_with_lstm(df, date_col, value_col, periods)
    
    if prophet_result['success'] and lstm_result['success']:
        # Weight by inverse MAE (lower error = higher weight)
        p_mae = prophet_result['metrics'].get('mae', 999)
        l_mae = lstm_result['metrics'].get('mae', 999)
        total = p_mae + l_mae
        if total > 0:
            p_weight = 1 - (p_mae / total)
            l_weight = 1 - (l_mae / total)
        else:
            p_weight = l_weight = 0.5
        
        p_df = prophet_result['forecast_df']
        l_df = lstm_result['forecast_df']
        
        # Merge on date, take weighted average of predictions
        min_len = min(len(p_df), len(l_df))
        ensemble_df = p_df.head(min_len).copy()
        ensemble_df['predicted'] = (
            p_weight * p_df['predicted'].head(min_len).values +
            l_weight * l_df['predicted'].head(min_len).values
        )
        
        logger.info(f"Ensemble: Prophet weight={p_weight:.2f}, LSTM weight={l_weight:.2f}")
        return {
            'forecast_df': ensemble_df,
            'model': 'Ensemble (Prophet + LSTM)',
            'metrics': {
                'prophet_mae': p_mae,
                'lstm_mae': l_mae,
                'weights': {'prophet': round(p_weight, 2), 'lstm': round(l_weight, 2)}
            },
            'success': True,
            'individual_results': {'prophet': prophet_result, 'lstm': lstm_result}
        }
    elif prophet_result['success']:
        logger.warning("LSTM failed, using Prophet only")
        return prophet_result
    elif lstm_result['success']:
        logger.warning("Prophet failed, using LSTM only")
        return lstm_result
    else:
        logger.error("Both Prophet and LSTM failed")
        return {
            'forecast_df': pd.DataFrame(),
            'model': 'None',
            'metrics': {},
            'success': False,
            'error': 'Both forecasting models failed'
        }
