import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
import pickle
import os
import datetime
from config import AI_MODEL_PATH
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("ai_model.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("AIModel")

class AIModelWrapper:
    """Wrapper class for AI model functionality"""

    def __init__(self, model_path="model.pkl"):
        self.model_path = model_path
        self.model = None
        self.last_training_time = None
        self.load_model()

    def load_model(self):
        """Load model from disk if it exists"""
        try:
            if os.path.exists(self.model_path):
                with open(self.model_path, 'rb') as f:
                    self.model = pickle.load(f)
                logger.info(f"Model loaded from {self.model_path}")
                return True
            else:
                logger.info("No existing model found, using default parameters")
                return False
        except Exception as e:
            logger.error(f"Error loading model: {e}")
            return False

    def save_model(self):
        """Save model to disk"""
        try:
            with open(self.model_path, 'wb') as f:
                pickle.dump(self.model, f)
            logger.info(f"Model saved to {self.model_path}")
            return True
        except Exception as e:
            logger.error(f"Error saving model: {e}")
            return False

    def predict(self, features):
        """Make prediction using the model"""
        try:
            # If no model is loaded, use a simple rule-based approach
            if self.model is None:
                # Simple rule-based prediction (example)
                if 'rsi' in features and 'macd_diff' in features:
                    if features['rsi'] > 70 and features['macd_diff'] < 0:
                        return 'SHORT'
                    elif features['rsi'] < 30 and features['macd_diff'] > 0:
                        return 'LONG'
                return None

            # Use the actual model for prediction if available
            # This is a placeholder - implement actual prediction logic
            return self.model.predict(features)
        except Exception as e:
            logger.error(f"Error making prediction: {e}")
            return None

    def train(self, training_data):
        """Train the model with new data"""
        try:
            # This is a placeholder - implement actual training logic
            logger.info(f"Training model with {len(training_data)} samples")

            # Simple example (not functional)
            # self.model = SomeMLModel()
            # self.model.fit(training_data)

            self.last_training_time = datetime.now()
            self.save_model()
            return True
        except Exception as e:
            logger.error(f"Error training model: {e}")
            return False

    def close(self):
        """Clean up resources"""
        try:
            if self.model and hasattr(self.model, 'close'):
                self.model.close()
            return True
        except Exception as e:
            logger.error(f"Error closing model: {e}")
            return False

class TrendDetectionModel:
    def __init__(self, data_processor):
        self.model = None
        self.scaler = StandardScaler()
        self.data_processor = data_processor
        self.last_training = datetime.datetime.now() - datetime.timedelta(days=1)
        self.load_model()

    def load_model(self):
        """Load model from disk if it exists"""
        if os.path.exists(AI_MODEL_PATH):
            try:
                with open(AI_MODEL_PATH, 'rb') as f:
                    model_data = pickle.load(f)
                    self.model = model_data['model']
                    self.scaler = model_data['scaler']
                print(f"Loaded AI model from {AI_MODEL_PATH}")
            except Exception as e:
                print(f"Error loading model: {e}")
                self.model = RandomForestClassifier(n_estimators=100, random_state=42)
        else:
            print("No existing model found, will train a new one")
            self.model = RandomForestClassifier(n_estimators=100, random_state=42)

    def save_model(self):
        """Save model to disk"""
        os.makedirs(os.path.dirname(AI_MODEL_PATH), exist_ok=True)
        model_data = {
            'model': self.model,
            'scaler': self.scaler
        }
        with open(AI_MODEL_PATH, 'wb') as f:
            pickle.dump(model_data, f)
        print(f"Saved AI model to {AI_MODEL_PATH}")

    def prepare_features(self, df):
        """Prepare features for the AI model"""
        if df is None or len(df) < 10:
            return None

        # Select relevant features
        features = df[['price_pct_change', 'rsi', 'macd', 'macd_diff', 'volume']].copy()

        # Add additional features
        features['price_dist_from_vwap'] = (df['price'] - df['vwap']) / df['vwap'] * 100
        features['price_dist_from_bb_upper'] = (df['price'] - df['bb_upper']) / df['bb_upper'] * 100
        features['price_dist_from_bb_lower'] = (df['price'] - df['bb_lower']) / df['bb_lower'] * 100

        # Handle NaN values
        features = features.fillna(0)

        return features

    def predict_trend(self, symbol):
        """Predict trend (LONG, SHORT, or NEUTRAL) for a symbol"""
        # Check if model needs retraining (once per day)
        now = datetime.datetime.now()
        if (now - self.last_training).days >= 1:
            self.train_model()
            self.last_training = now

        # Get latest data
        df = self.data_processor.calculate_indicators(symbol)
        if df is None or len(df) < 10:
            return 'NEUTRAL', 0.0

        # Prepare features
        features = self.prepare_features(df)
        if features is None:
            return 'NEUTRAL', 0.0

        # Get the latest feature set
        latest_features = features.iloc[-1:].values

        # Scale features
        scaled_features = self.scaler.transform(latest_features)

        # Make prediction
        if self.model is not None:
            prediction = self.model.predict(scaled_features)[0]
            probabilities = self.model.predict_proba(scaled_features)[0]

            confidence = max(probabilities)

            if prediction == 1:  # LONG
                return 'LONG', confidence
            elif prediction == -1:  # SHORT
                return 'SHORT', confidence

        return 'NEUTRAL', 0.0

    def evaluate_signal(self, signal_data):
        """
        Evaluate a signal detected by the data processor using the AI model
        Returns True if the signal should be sent, False otherwise
        """
        if signal_data is None:
            return False

        symbol = signal_data['symbol']
        trend_from_processor = signal_data['trend']

        # Get AI prediction
        ai_trend, confidence = self.predict_trend(symbol)

        # Only send signal if AI agrees with at least 65% confidence
        if ai_trend == trend_from_processor and confidence >= 0.65:
            return True

        return False

    def train_model(self):
        """Train the AI model using recent market data"""
        print("Training AI model...")

        # Collect training data from multiple symbols
        all_features = []
        all_labels = []

        # Get symbols with enough data
        symbols = self.data_processor.symbol_data.keys()

        for symbol in symbols:
            df = self.data_processor.calculate_indicators(symbol)
            if df is None or len(df) < 50:  # Need enough historical data
                continue

            # Prepare features
            features = self.prepare_features(df)
            if features is None:
                continue

            # Create labels: 1 for LONG, -1 for SHORT, 0 for NEUTRAL
            # A price change of >2% within the next 12 ticks is considered a trend
            future_returns = df['price'].pct_change(periods=12).shift(-12) * 100
            labels = np.zeros(len(df))
            labels[future_returns > 2.0] = 1  # LONG
            labels[future_returns < -2.0] = -1  # SHORT

            # Exclude the most recent data point (which we don't have a label for yet)
            features = features.iloc[:-12]
            labels = labels[:-12]

            if len(features) > 0:
                all_features.append(features)
                all_labels.append(labels)

        if not all_features:
            print("Not enough data to train the model")
            return

        # Combine data from all symbols
        X = pd.concat(all_features, axis=0)
        y = np.concatenate(all_labels)

        # Scale features
        X_scaled = self.scaler.fit_transform(X)

        # Train model
        self.model.fit(X_scaled, y)

        # Save the trained model
        self.save_model()
        print("AI model training completed")
