import numpy as np
import pandas as pd
import sqlite3
import logging
import os
import pickle
import time
from datetime import datetime
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

logger = logging.getLogger(__name__)


class EnhancedAIModel:
    def __init__(self, db_path='data'):
        self.db_path = db_path
        self.models = {}
        self.scalers = {}
        self.min_data_points = 500  # Increased minimum data points for better training
        self.training_frequency = 100
        self.data_counter = {}
        self.model_dir = os.path.join(db_path, 'models')
        os.makedirs(self.model_dir, exist_ok=True)

        # Initialize performance tracking
        self.performance_metrics = {}

        # Load existing models if available
        self.load_models()

        # Call accelerate_training to speed up initial learning
        self.accelerate_training()

        logger.info("Enhanced AI model initialized")

    def load_models(self):
        """Load trained models if they exist"""
        for model_file in os.listdir(self.model_dir):
            if model_file.endswith('.pkl'):
                symbol = model_file.split('_')[0]
                model_path = os.path.join(self.model_dir, model_file)

                try:
                    with open(model_path, 'rb') as f:
                        model_data = pickle.load(f)

                    self.models[symbol] = model_data['model']
                    self.scalers[symbol] = model_data['scaler']
                    self.performance_metrics[symbol] = model_data.get('metrics', {})

                    logger.info(f"Loaded model for {symbol}")
                except Exception as e:
                    logger.error(f"Error loading model for {symbol}: {e}")

    def save_model(self, symbol):
        """Save trained model to disk"""
        if symbol in self.models and symbol in self.scalers:
            model_data = {
                'model': self.models[symbol],
                'scaler': self.scalers[symbol],
                'metrics': self.performance_metrics.get(symbol, {}),
                'updated_at': datetime.now().isoformat()
            }

            model_path = os.path.join(self.model_dir, f"{symbol}_model.pkl")

            with open(model_path, 'wb') as f:
                pickle.dump(model_data, f)

            logger.info(f"Saved model for {symbol}")

    def get_training_data(self, symbol, lookback=20):
        """Get enhanced training data with more features and lookback periods"""
        conn = sqlite3.connect(os.path.join(self.db_path, 'ai_model.db'))
        cursor = conn.cursor()

        # Get all feature data for this symbol
        cursor.execute('''
        SELECT id, price_change_1m, price_change_5m, price_change_15m, price_change_1h,
               volume_change_1m, volume_change_5m, rsi_value, macd_histogram, 
               ema_crossover, timestamp
        FROM model_features
        WHERE symbol = ?
        ORDER BY timestamp
        ''', (symbol,))

        feature_rows = cursor.fetchall()

        if not feature_rows or len(feature_rows) < self.min_data_points:
            conn.close()
            return None, None, None

        # Get market data for future price changes (for labeling)
        conn_market = sqlite3.connect(os.path.join(self.db_path, 'market_data.db'))
        cursor_market = conn_market.cursor()

        cursor_market.execute('''
        SELECT price, timestamp FROM market_data 
        WHERE symbol = ? 
        ORDER BY timestamp
        ''', (symbol,))

        market_data = cursor_market.fetchall()
        conn_market.close()

        if not market_data or len(market_data) < len(feature_rows):
            conn.close()
            return None, None, None

        # Create a mapping of timestamps to prices for easier lookup
        price_map = {ts: price for price, ts in market_data}

        # Prepare features and labels
        feature_ids = []
        features = []
        labels = []
        timestamps = []

        for i in range(lookback, len(feature_rows)):
            # Get current feature row
            feature_id, *feature_values, timestamp = feature_rows[i]

            # Create a window of features (lookback period)
            window_features = []
            for j in range(i - lookback, i + 1):
                _, *window_values, _ = feature_rows[j]
                window_features.extend(window_values)

            # Find future price for labeling
            future_timestamp = timestamp + (3600 * 1000)  # 1 hour in the future

            # Find the closest timestamp in our price data
            closest_timestamps = sorted(price_map.keys(), key=lambda x: abs(x - future_timestamp))
            if not closest_timestamps:
                continue

            closest_timestamp = closest_timestamps[0]

            # Skip if the closest timestamp is too far from our target
            if abs(closest_timestamp - future_timestamp) > (15 * 60 * 1000):  # 15 minutes
                continue

            future_price = price_map[closest_timestamp]
            current_price = price_map.get(timestamp, None)

            if not current_price:
                continue

            # Calculate price change percentage
            price_change = ((future_price - current_price) / current_price) * 100

            # Create label based on price change threshold
            threshold = 3.0  # Configurable

            if price_change > threshold:
                label = 1  # Long signal
            elif price_change < -threshold:
                label = -1  # Short signal
            else:
                label = 0  # Neutral

            feature_ids.append(feature_id)
            features.append(window_features)
            labels.append(label)
            timestamps.append(timestamp)

        conn.close()

        if not features:
            return None, None, None

        return np.array(features), np.array(labels), feature_ids

    def train_advanced_models(self, symbol):
        """Train both traditional and deep learning models"""
        features, labels, feature_ids = self.get_training_data(symbol)

        if features is None or len(features) < self.min_data_points:
            logger.info(f"Not enough data to train model for {symbol}")
            return False

        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            features, labels, test_size=0.2, random_state=42, stratify=labels
        )

        # Scale features
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)

        # Train ensemble model
        ensemble_model = GradientBoostingClassifier(
            n_estimators=100,
            learning_rate=0.1,
            max_depth=5,
            random_state=42
        )

        ensemble_model.fit(X_train_scaled, y_train)

        # Evaluate ensemble model
        y_pred = ensemble_model.predict(X_test_scaled)

        accuracy = accuracy_score(y_test, y_pred)
        precision = precision_score(y_test, y_pred, average='weighted', zero_division=0)
        recall = recall_score(y_test, y_pred, average='weighted', zero_division=0)
        f1 = f1_score(y_test, y_pred, average='weighted', zero_division=0)

        # Store model and metrics
        self.models[symbol] = ensemble_model
        self.scalers[symbol] = scaler
        self.performance_metrics[symbol] = {
            'accuracy': accuracy,
            'precision': precision,
            'recall': recall,
            'f1_score': f1,
            'training_samples': len(X_train),
            'last_trained': datetime.now().isoformat()
        }

        # Save models
        self.save_model(symbol)

        logger.info(f"Trained models for {symbol} with accuracy: {accuracy:.4f}")
        return True

    def predict(self, symbol, features_id):
        """Make predictions using the trained models"""
        # Get feature data
        conn = sqlite3.connect(os.path.join(self.db_path, 'ai_model.db'))
        cursor = conn.cursor()

        cursor.execute('''
        SELECT symbol, price_change_1m, price_change_5m, price_change_15m, price_change_1h,
               volume_change_1m, volume_change_5m, rsi_value, macd_histogram, 
               ema_crossover, timestamp
        FROM model_features
        WHERE id = ?
        ''', (features_id,))

        row = cursor.fetchone()

        if not row:
            conn.close()
            return None, 0.0

        symbol = row[0]
        feature_values = row[1:10]  # All features except timestamp
        timestamp = row[10]

        # Check if we need to train the model
        if symbol not in self.data_counter:
            self.data_counter[symbol] = 0

        self.data_counter[symbol] += 1

        if (symbol not in self.models or
                self.data_counter[symbol] % self.training_frequency == 0):
            self.train_advanced_models(symbol)

        # If we still don't have a model, return neutral prediction
        if symbol not in self.models:
            prediction_type = "NEUTRAL"
            confidence = 0.0

            # Save prediction to database
            cursor.execute('''
            INSERT INTO model_predictions 
            (symbol, prediction_type, confidence_score, features_id, timestamp)
            VALUES (?, ?, ?, ?, ?)
            ''', (symbol, prediction_type, confidence, features_id, timestamp))

            conn.commit()
            conn.close()

            return prediction_type, confidence

        # Get lookback features for this symbol
        cursor.execute('''
        SELECT price_change_1m, price_change_5m, price_change_15m, price_change_1h,
               volume_change_1m, volume_change_5m, rsi_value, macd_histogram, 
               ema_crossover
        FROM model_features
        WHERE symbol = ? AND timestamp < ?
        ORDER BY timestamp DESC
        LIMIT 20
        ''', (symbol, timestamp))

        lookback_rows = cursor.fetchall()

        # If we don't have enough lookback data, use the ensemble model only
        if len(lookback_rows) < 20:
            # Transform features for ensemble model
            X = np.array(feature_values).reshape(1, -1)
            X_scaled = self.scalers[symbol].transform(X)

            # Get prediction from ensemble model
            prediction = self.models[symbol].predict(X_scaled)[0]
            probabilities = self.models[symbol].predict_proba(X_scaled)[0]

            # Map prediction to type and get confidence
            if prediction == -1:  # Short
                prediction_type = "SHORT"
                confidence = probabilities[0]
            elif prediction == 1:  # Long
                prediction_type = "LONG"
                confidence = probabilities[2]
            else:  # Neutral
                prediction_type = "NEUTRAL"
                confidence = probabilities[1]
        else:
            # Prepare data for both models
            window_features = []

            # Add lookback features (oldest to newest)
            for row in reversed(lookback_rows):
                window_features.extend(row)

            # Add current features
            window_features.extend(feature_values)

            # Make prediction with ensemble model
            X_ensemble = np.array(window_features).reshape(1, -1)
            X_ensemble_scaled = self.scalers[symbol].transform(X_ensemble)

            ensemble_prediction = self.models[symbol].predict(X_ensemble_scaled)[0]
            ensemble_probabilities = self.models[symbol].predict_proba(X_ensemble_scaled)[0]

            # Use only ensemble model
            if ensemble_prediction == -1:  # Short
                prediction_type = "SHORT"
                confidence = ensemble_probabilities[0]
            elif ensemble_prediction == 1:  # Long
                prediction_type = "LONG"
                confidence = ensemble_probabilities[2]
            else:  # Neutral
                prediction_type = "NEUTRAL"
                confidence = ensemble_probabilities[1]

        # Save prediction to database
        cursor.execute('''
        INSERT INTO model_predictions 
        (symbol, prediction_type, confidence_score, features_id, timestamp)
        VALUES (?, ?, ?, ?, ?)
        ''', (symbol, prediction_type, confidence, features_id, timestamp))

        conn.commit()
        conn.close()

        return prediction_type, confidence

    def update_prediction_outcome(self, prediction_id, actual_outcome, accuracy):
        """Update the prediction with actual outcome and accuracy"""
        conn = sqlite3.connect(os.path.join(self.db_path, 'ai_model.db'))
        cursor = conn.cursor()

        cursor.execute('''
        UPDATE model_predictions
        SET actual_outcome = ?, accuracy = ?
        WHERE id = ?
        ''', (actual_outcome, accuracy, prediction_id))

        conn.commit()
        conn.close()

        logger.info(f"Updated prediction {prediction_id} with outcome: {actual_outcome}, accuracy: {accuracy}")

    def get_model_performance(self, symbol):
        """Get performance metrics for a specific symbol"""
        if symbol in self.performance_metrics:
            return self.performance_metrics[symbol]
        return None

    def get_all_performance_metrics(self):
        """Get performance metrics for all models"""
        return self.performance_metrics

    def accelerate_training(self):
        """Force more frequent model training during initial learning phase"""
        # Reduce the training frequency
        self.training_frequency = 50  # Instead of 100
        # Reduce minimum data points required for training
        self.min_data_points = 50  # Instead of 500
        self.min_data_points = 50  # Instead of 500