"""LSTM time series forecasting using TensorFlow/Keras."""
import logging
import os
import numpy as np
import pandas as pd
from typing import Optional

# Suppress TF warnings
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'

logger = logging.getLogger(__name__)

def forecast_with_lstm(
    df: pd.DataFrame,
    date_col: str = 'date',
    value_col: str = 'value',
    periods: int = 30
) -> dict:
    """Generate forecast using LSTM neural network.
    
    Args:
        df: DataFrame with date and value columns
        date_col: Name of the date column
        value_col: Name of the value column  
        periods: Number of future periods to forecast
    
    Returns:
        dict with 'forecast_df', 'model', 'metrics'
    """
    try:
        from sklearn.preprocessing import MinMaxScaler
        from tensorflow.keras.models import Sequential
        from tensorflow.keras.layers import LSTM, Dense
        
        # Prepare data
        data_df = df[[date_col, value_col]].copy()
        data_df[date_col] = pd.to_datetime(data_df[date_col])
        data_df = data_df.dropna().sort_values(date_col).reset_index(drop=True)
        
        if len(data_df) < 50:
            raise ValueError(f"Need at least 50 data points for LSTM, got {len(data_df)}")
        
        values = data_df[value_col].values.reshape(-1, 1)
        
        # Normalize
        scaler = MinMaxScaler(feature_range=(0, 1))
        scaled_values = scaler.fit_transform(values)
        
        # Create sequences
        lookback = 30
        if len(scaled_values) <= lookback:
            raise ValueError("Data length must be greater than lookback window (30)")
            
        X, y = [], []
        for i in range(lookback, len(scaled_values)):
            X.append(scaled_values[i-lookback:i, 0])
            y.append(scaled_values[i, 0])
        X, y = np.array(X), np.array(y)
        
        # Reshape for LSTM [samples, time steps, features]
        X = np.reshape(X, (X.shape[0], X.shape[1], 1))
        
        # Build model
        model = Sequential()
        model.add(LSTM(50, return_sequences=True, input_shape=(X.shape[1], 1)))
        model.add(LSTM(50, return_sequences=False))
        model.add(Dense(1))
        
        model.compile(optimizer='adam', loss='mean_squared_error')
        
        # Train
        model.fit(X, y, epochs=50, batch_size=16, verbose=0)
        
        # Calculate metrics on training set
        train_pred_scaled = model.predict(X, verbose=0)
        train_pred = scaler.inverse_transform(train_pred_scaled)
        actual = scaler.inverse_transform(y.reshape(-1, 1))
        
        mae = np.mean(np.abs(actual - train_pred))
        rmse = np.sqrt(np.mean((actual - train_pred)**2))
        
        # Forecast future
        last_sequence = scaled_values[-lookback:]
        current_sequence = last_sequence.reshape((1, lookback, 1))
        
        future_preds = []
        for _ in range(periods):
            pred = model.predict(current_sequence, verbose=0)[0, 0]
            future_preds.append(pred)
            
            # Update sequence by removing oldest and adding new prediction
            current_sequence = np.append(current_sequence[:, 1:, :], [[[pred]]], axis=1)
            
        future_preds_unscaled = scaler.inverse_transform(np.array(future_preds).reshape(-1, 1))
        
        # Create results DataFrame
        last_date = data_df[date_col].iloc[-1]
        future_dates = pd.date_range(start=last_date + pd.Timedelta(days=1), periods=periods)
        
        result_df = pd.DataFrame({
            'date': future_dates,
            'predicted': future_preds_unscaled.flatten()
        })
        
        # Mock confidence intervals based on RMSE
        result_df['lower_bound'] = result_df['predicted'] - (1.96 * rmse)
        result_df['upper_bound'] = result_df['predicted'] + (1.96 * rmse)
        
        # Combine historical predictions with future predictions to match Prophet format closely if needed
        # For simplicity, returning just the future predictions as requested, but Prophet returns both.
        # We'll just build a complete DF matching the structure
        hist_dates = data_df[date_col].iloc[lookback:].values
        hist_preds = train_pred.flatten()
        
        hist_df = pd.DataFrame({
            'date': hist_dates,
            'predicted': hist_preds,
            'lower_bound': hist_preds - (1.96 * rmse),
            'upper_bound': hist_preds + (1.96 * rmse)
        })
        
        final_df = pd.concat([hist_df, result_df], ignore_index=True)
        
        logger.info(f"LSTM forecast done. MAE: {mae:.2f}, RMSE: {rmse:.2f}")
        return {
            'forecast_df': final_df,
            'model': 'LSTM',
            'metrics': {'mae': round(float(mae), 2), 'rmse': round(float(rmse), 2)},
            'success': True
        }
        
    except Exception as e:
        logger.error(f"LSTM forecasting failed: {e}")
        return {'forecast_df': pd.DataFrame(), 'model': 'LSTM', 'metrics': {}, 'success': False, 'error': str(e)}
