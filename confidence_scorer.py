import numpy as np
import pandas as pd
import sqlite3
import logging
import os
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class AdvancedConfidenceScorer:
    def __init__(self, db_path='data'):
        self.db_path = db_path
        self.market_regimes = {}  # Store detected market regimes by symbol
        self.volatility_levels = {}  # Store volatility levels by symbol
        
        logger.info("Advanced confidence scorer initialized")
    
    def detect_market_regime(self, symbol):
        """Detect the current market regime (trending, ranging, volatile)"""
        conn = sqlite3.connect(os.path.join(self.db_path, 'market_data.db'))
        
        # Get recent price data (last 24 hours)
        end_time = int(datetime.now().timestamp() * 1000)
        start_time = end_time - (24 * 3600 * 1000)  # 24 hours in milliseconds
        
        query = '''
        SELECT price, timestamp FROM market_data
        WHERE symbol = ? AND timestamp BETWEEN ? AND ?
        ORDER BY timestamp
        '''
        
        df = pd.read_sql_query(query, conn, params=(symbol, start_time, end_time))
        conn.close()
        
        if len(df) < 100:  # Need enough data points
            return "UNKNOWN"
        
        # Calculate returns
        df['returns'] = df['price'].pct_change()
        
        # Calculate volatility (standard deviation of returns)
        volatility = df['returns'].std() * 100  # Convert to percentage
        
        # Store volatility level
        if volatility < 0.5:
            volatility_level = "LOW"
        elif volatility < 2.0:
            volatility_level = "MEDIUM"
        else:
            volatility_level = "HIGH"
        
        self.volatility_levels[symbol] = volatility_level
        
        # Calculate directional movement
        price_change = (df['price'].iloc[-1] / df['price'].iloc[0] - 1) * 100
        
        # Calculate range as percentage of average price
        price_range = (df['price'].max() - df['price'].min()) / df['price'].mean() * 100
        
        # Determine market regime
        if abs(price_change) > 5 and volatility > 1.5:
            regime = "TRENDING"
        elif price_range < 3 and volatility < 1.0:
            regime = "RANGING"
        elif volatility > 2.5:
            regime = "VOLATILE"
        else:
            regime = "MIXED"
        
        # Store market regime
        self.market_regimes[symbol] = regime
        
        return regime
    
    def adjust_confidence(self, symbol, prediction_type, base_confidence):
        """Adjust confidence score based on market conditions"""
        # Detect market regime if not already done
        if symbol not in self.market_regimes:
            self.detect_market_regime(symbol)
        
        regime = self.market_regimes.get(symbol, "UNKNOWN")
        volatility_level = self.volatility_levels.get(symbol, "MEDIUM")
        
        # Get technical indicators
        conn = sqlite3.connect(os.path.join(self.db_path, 'indicators.db'))
        
        query = '''
        SELECT rsi_14, macd, macd_signal, macd_histogram, ema_9, ema_21
        FROM indicators
        WHERE symbol = ?
        ORDER BY timestamp DESC
        LIMIT 1
        '''
        
        cursor = conn.cursor()
        cursor.execute(query, (symbol,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return base_confidence
        
        rsi, macd, macd_signal, macd_hist, ema_9, ema_21 = row
        
        # Initialize confidence adjustment factors
        regime_factor = 1.0
        indicator_factor = 1.0
        
        # Adjust based on market regime
        if regime == "TRENDING":
            if prediction_type in ["LONG", "SHORT"]:
                regime_factor = 1.2  # Boost confidence in trending markets for directional signals
            else:
                regime_factor = 0.8  # Reduce confidence for neutral signals in trending markets
        elif regime == "RANGING":
            if prediction_type == "NEUTRAL":
                regime_factor = 1.2  # Boost confidence for neutral signals in ranging markets
            else:
                regime_factor = 0.9  # Slightly reduce confidence for directional signals
        elif regime == "VOLATILE":
            regime_factor = 0.8  # Reduce confidence in volatile markets
        
        # Adjust based on indicator confirmation
        if prediction_type == "LONG":
            # Check if indicators confirm bullish signal
            if rsi > 70:  # Strong RSI
                indicator_factor += 0.1
            elif rsi < 40:  # Contradicting RSI
                indicator_factor -= 0.2
                
            if macd_hist > 0 and macd > macd_signal:  # Bullish MACD
                indicator_factor += 0.1
            elif macd_hist < 0 and macd < macd_signal:  # Bearish MACD
                indicator_factor -= 0.2
                
            if ema_9 > ema_21:  # Bullish EMA crossover
                indicator_factor += 0.1
            else:
                indicator_factor -= 0.1
                
        elif prediction_type == "SHORT":
            # Check if indicators confirm bearish signal
            if rsi < 30:  # Strong RSI
                indicator_factor += 0.1
            elif rsi > 60:  # Contradicting RSI
                indicator_factor -= 0.2
                
            if macd_hist < 0 and macd < macd_signal:  # Bearish MACD
                indicator_factor += 0.1
            elif macd_hist > 0 and macd > macd_signal:  # Bullish MACD
                indicator_factor -= 0.2
                
            if ema_9 < ema_21:  # Bearish EMA crossover
                indicator_factor += 0.1
            else:
                indicator_factor -= 0.1
        
        # Adjust based on volatility
        volatility_factor = 1.0
        if volatility_level == "HIGH":
            volatility_factor = 0.9  # Reduce confidence in high volatility
        elif volatility_level == "LOW":
            volatility_factor = 1.1  # Increase confidence in low volatility
        
        # Calculate final adjusted confidence
        adjusted_confidence = base_confidence * regime_factor * indicator_factor * volatility_factor
        
        # Ensure confidence is between 0 and 1
        adjusted_confidence = max(0.0, min(1.0, adjusted_confidence))
        
        logger.debug(f"Adjusted confidence for {symbol} {prediction_type}: {base_confidence:.4f} -> {adjusted_confidence:.4f}")
        
        return adjusted_confidence
    
    def get_dynamic_threshold(self, symbol):
        """Get dynamic confidence threshold based on market conditions"""
        # Default threshold
        base_threshold = 0.7
        
        # Adjust based on market regime
        if symbol not in self.market_regimes:
            self.detect_market_regime(symbol)
        
        regime = self.market_regimes.get(symbol, "UNKNOWN")
        volatility_level = self.volatility_levels.get(symbol, "MEDIUM")
        
        # Adjust threshold based on regime
        if regime == "TRENDING":
            regime_adjustment = -0.05  # Lower threshold in trending markets
        elif regime == "RANGING":
            regime_adjustment = 0.05  # Higher threshold in ranging markets
        elif regime == "VOLATILE":
            regime_adjustment = 0.1  # Much higher threshold in volatile markets
        else:
            regime_adjustment = 0.0
        
        # Adjust threshold based on volatility
        if volatility_level == "HIGH":
            volatility_adjustment = 0.1  # Higher threshold in high volatility
        elif volatility_level == "LOW":
            volatility_adjustment = -0.05  # Lower threshold in low volatility
        else:
            volatility_adjustment = 0.0
        
        # Calculate final threshold
        threshold = base_threshold + regime_adjustment + volatility_adjustment
        
        # Ensure threshold is between 0.5 and 0.9
        threshold = max(0.5, min(0.9, threshold))
        
        return threshold
