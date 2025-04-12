import numpy as np
import pandas as pd
import sqlite3
import logging
import os
import pickle
from datetime import datetime
from sklearn.svm import SVR
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, r2_score

logger = logging.getLogger(__name__)


class SVRModel:
    def __init__(self, db_path='data'):
        self.db_path = db_path
        self.models = {}  # Dictionary to store models for each symbol
        self.scalers = {}  # Dictionary to store scalers for each symbol
        self.model_dir = os.path.join(db_path, 'models', 'svr')
        os.makedirs(self.model_dir, exist_ok=True)

        # Load existing models
        self.load_models()

        logger.info("SVR model initialized")

    def load_models(self):
        """Load trained models from disk"""
        if not os.path.exists(self.model_dir):
            return

        for model_file in os.listdir(self.model_dir):
            if model_file.endswith('.pkl'):
                symbol = model_file.split('_')[0]
                model_path = os.path.join(self.model_dir, model_file)

                try:
                    with open(model_path, 'rb') as f:
                        model_data = pickle.load(f)

                    self.models[symbol] = model_data['model']
                    self.scalers[symbol] = model_data['scaler']

                    logger.info(f"Loaded SVR model for {symbol}")
                except Exception as e:
                    logger.error(f"Error loading SVR model for {symbol}: {e}")

    def save_model(self, symbol):
        """Save model to disk"""
        if symbol in self.models and symbol in self.scalers:
            model_data = {
                'model': self.models[symbol],
                'scaler': self.scalers[symbol],
                'updated_at': datetime.now().isoformat()
            }

            model_path = os.path.join(self.model_dir, f"{symbol}_svr.pkl")

            with open(model_path, 'wb') as f:
                pickle.dump(model_data, f)

            logger.info(f"Saved SVR model for {symbol}")

    def get_training_data(self, symbol, lookback=10, prediction_horizon=12):
        """Get training data for SVR model"""
        conn = sqlite3.connect(os.path.join(self.db_path, 'market_data.db'))

        # Get price data for this symbol
        query = '''
        SELECT price, timestamp 
        FROM market_data
        WHERE symbol = ?
        ORDER BY timestamp
        '''

        df = pd.read_sql_query(query, conn, params=(symbol,))
        conn.close()

        if len(df) < lookback + prediction_horizon + 50:
            logger.info(f"Not enough data for {symbol} to train SVR model")
            return None, None

        # Create features and target
        X = []
        y = []

        for i in range(len(df) - lookback - prediction_horizon):
            # Features: price changes over lookback period
            prices = df['price'].iloc[i:i + lookback].values
            price_changes = np.diff(prices) / prices[:-1] * 100

            # Target: price change after prediction_horizon
            current_price = df['price'].iloc[i + lookback - 1]
            future_price = df['price'].iloc[i + lookback + prediction_horizon - 1]
            price_change_pct = (future_price - current_price) / current_price * 100

            X.append(price_changes)
            y.append(price_change_pct)

        return np.array(X), np.array(y)

    def train(self, symbol):
        """Train SVR model for a symbol"""
        X, y = self.get_training_data(symbol)

        if X is None or len(X) < 100:
            logger.info(f"Not enough data to train SVR model for {symbol}")
            return False

        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )

        # Scale features
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)

        # Train SVR model
        svr = SVR(kernel='rbf', C=100, gamma=0.1, epsilon=0.1)
        svr.fit(X_train_scaled, y_train)

        # Evaluate model
        y_pred = svr.predict(X_test_scaled)
        mse = mean_squared_error(y_test, y_pred)
        r2 = r2_score(y_test, y_pred)

        logger.info(f"Trained SVR model for {symbol} - MSE: {mse:.4f}, R²: {r2:.4f}")

        # Save model and scaler
        self.models[symbol] = svr
        self.scalers[symbol] = scaler
        self.save_model(symbol)

        return True

    def predict(self, symbol, features_id=None):
        """
        Predict price movement for a symbol
        Returns prediction type (LONG, SHORT, NEUTRAL) and confidence
        """
        # If we don't have a model for this symbol, train one
        if symbol not in self.models:
            success = self.train(symbol)
            if not success:
                return "NEUTRAL", 0.0

        # Get recent price data
        conn = sqlite3.connect(os.path.join(self.db_path, 'market_data.db'))

        query = '''
            SELECT price FROM market_data
            WHERE symbol = ?
            ORDER BY timestamp DESC
            LIMIT 20
            '''

        cursor = conn.cursor()
        cursor.execute(query, (symbol,))
        prices = [row[0] for row in cursor.fetchall()]
        conn.close()

        if len(prices) < 11:  # Need at least 11 prices to calculate 10 changes
            return "NEUTRAL", 0.0

        # Reverse to get chronological order
        prices = prices[::-1]

        # Calculate price changes
        price_changes = np.diff(prices) / prices[:-1] * 100

        # Ensure we have the right number of features
        if len(price_changes) < 10:
            return "NEUTRAL", 0.0

        # Use the last 10 price changes as features
        features = price_changes[-10:].reshape(1, -1)

        # Scale features
        features_scaled = self.scalers[symbol].transform(features)

        # Make prediction
        predicted_change = self.models[symbol].predict(features_scaled)[0]

        # Convert to prediction type and confidence
        threshold = 3.0  # Configurable

        if predicted_change > threshold:
            prediction_type = "LONG"
            confidence = min(0.95, 0.5 + abs(predicted_change) / 20)
        elif predicted_change < -threshold:
            prediction_type = "SHORT"
            confidence = min(0.95, 0.5 + abs(predicted_change) / 20)
        else:
            prediction_type = "NEUTRAL"
            confidence = 0.5 - abs(predicted_change) / 10
            confidence = max(0.1, min(0.5, confidence))

        logger.debug(
            f"SVR prediction for {symbol}: {prediction_type} with {confidence:.2f} confidence (predicted change: {predicted_change:.2f}%)")

        return prediction_type, confidence

    def batch_train(self, symbols=None):
        """Train models for multiple symbols"""
        if symbols is None:
            # Get all symbols from market data
            conn = sqlite3.connect(os.path.join(self.db_path, 'market_data.db'))
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT symbol FROM market_data")
            symbols = [row[0] for row in cursor.fetchall()]
            conn.close()

        success_count = 0
        for symbol in symbols:
            try:
                if self.train(symbol):
                    success_count += 1
            except Exception as e:
                logger.error(f"Error training SVR model for {symbol}: {e}")

        logger.info(f"Batch training completed. Trained {success_count}/{len(symbols)} models successfully.")
        return success_count
