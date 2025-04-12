import datetime
import random
import os
import pickle
from config import AI_MODEL_PATH

class SimpleTrendDetectionModel:
    def __init__(self, data_processor):
        self.data_processor = data_processor
        self.model_data = {
            'last_updated': datetime.datetime.now(),
            'confidence_factor': 0.7  # Initial confidence factor
        }
        self.load_model()

    def load_model(self):
        """Load simplified model data if exists"""
        if os.path.exists(AI_MODEL_PATH):
            try:
                with open(AI_MODEL_PATH, 'rb') as f:
                    self.model_data = pickle.load(f)
                print(f"Loaded model data from {AI_MODEL_PATH}")
            except Exception as e:
                print(f"Error loading model: {e}")
        else:
            print("No existing model found, using default parameters")

    def save_model(self):
        """Save model data to file"""
        os.makedirs(os.path.dirname(AI_MODEL_PATH), exist_ok=True)
        with open(AI_MODEL_PATH, 'wb') as f:
            pickle.dump(self.model_data, f)
        print(f"Saved model data to {AI_MODEL_PATH}")

    def predict_trend(self, symbol):
        """
        Simplified trend prediction - uses basic indicators without complex ML
        Returns: trend (LONG, SHORT, NEUTRAL), confidence (0.0-1.0)
        """
        result = self.data_processor.calculate_indicators(symbol)
        if not result or len(result) < 10:
            return "NEUTRAL", 0.0

        # Get the latest indicators
        latest = result[-1]

        # Price change over last 5 candles
        recent_changes = [item['price_pct_change'] for item in result[-5:]]
        avg_recent_change = sum(recent_changes) / len(recent_changes)

        # Determine trend based on indicators
        if (latest['rsi'] > 60 and latest['macd_diff'] > 0 and avg_recent_change > 0):
            confidence = min(0.95, max(0.65, self.model_data['confidence_factor'] *
                              abs(latest['macd_diff']) * (latest['rsi'] / 100)))
            return "LONG", confidence

        elif (latest['rsi'] < 40 and latest['macd_diff'] < 0 and avg_recent_change < 0):
            confidence = min(0.95, max(0.65, self.model_data['confidence_factor'] *
                              abs(latest['macd_diff']) * ((100 - latest['rsi']) / 100)))
            return "SHORT", confidence

        return "NEUTRAL", 0.0

    def evaluate_signal(self, signal_data):
        """Evaluate signal quality using simplified approach"""
        if signal_data is None:
            return False

        symbol = signal_data['symbol']
        trend_from_processor = signal_data['trend']

        # Get simplified prediction
        ai_trend, confidence = self.predict_trend(symbol)

        # Only send signal if prediction agrees with at least 65% confidence
        if ai_trend == trend_from_processor and confidence >= 0.65:
            return True

        return False

    def train_model(self):
        """
        Simple training - just updates the confidence factor
        based on time and random adjustment to simulate learning
        """
        # Only update once per day
        now = datetime.datetime.now()
        days_since_update = (now - self.model_data['last_updated']).days

        if days_since_update >= 1:
            # Update confidence factor (simulated learning)
            adjustment = random.uniform(-0.05, 0.05)
            self.model_data['confidence_factor'] = max(0.6, min(0.8,
                                                      self.model_data['confidence_factor'] + adjustment))
            self.model_data['last_updated'] = now

            self.save_model()
            print(f"Updated model with new confidence factor: {self.model_data['confidence_factor']:.2f}")
            return True

        return False
