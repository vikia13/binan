import os
import logging
import asyncio
import sqlite3
import time
from datetime import datetime
import json
import sys
import io
from dotenv import load_dotenv
from accuracy_tracker import AccuracyTracker
from ai_model_enhanced import EnhancedAIModel
from alert_system import AlertSystem
from ai_model import AIModelWrapper
from confidence_scorer import AdvancedConfidenceScorer
from performance_evaluator import PerformanceEvaluator
# Import original components
from websocket_client import WebSocketClient
from data_processor import DataProcessor
# Import adapters
from telegram_adapter import EnhancedTelegramBot
from database_adapter import DatabaseAdapter
# Set console encoding to UTF-8 to handle emoji characters
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("screener_enhanced.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("Main")

# Load environment variables
load_dotenv()


class EnhancedBinanceScreener:
    def __init__(self):
        self.db_path = 'data'
        os.makedirs(self.db_path, exist_ok=True)

        # Initialize database
        self.init_database()

        # Initialize components
        self.telegram_bot = EnhancedTelegramBot(
            os.getenv('TELEGRAM_TOKEN'),
            os.getenv('TELEGRAM_CHAT_ID')
        )

        self.data_processor = DataProcessor()

        # Initialize enhanced AI model
        self.ai_model = EnhancedAIModel(self.db_path)

        # Initialize confidence scorer
        self.confidence_scorer = AdvancedConfidenceScorer(self.db_path)

        # Initialize database adapter
        self.database = DatabaseAdapter(self.db_path)

        # Get the original telegram_bot if we're using our adapter
        if hasattr(self.telegram_bot, 'original_bot'):
            telegram_bot_to_use = self.telegram_bot.original_bot
        else:
            telegram_bot_to_use = self.telegram_bot

        # Initialize alert system with original components
        original_ai_model = AIModelWrapper()
        self.alert_system = AlertSystem(self.database, telegram_bot_to_use, original_ai_model)

        # Initialize WebSocket client with the correct URL
        websocket_url = "wss://fstream.binance.com/ws/!ticker@arr"
        self.websocket_client = WebSocketClient(websocket_url, self.handle_websocket_message)

        # Initialize performance evaluator
        self.performance_evaluator = PerformanceEvaluator(self.db_path)

        # Initialize accuracy tracker
        self.accuracy_tracker = AccuracyTracker(self.db_path, self.ai_model)

        # Setup background tasks
        self.setup_background_tasks()

        logger.info("Enhanced Binance Futures Screener initialized")

    def init_database(self):
        """Initialize all required databases"""
        logger.info("Initializing database...")

        # Create market_data.db
        conn = sqlite3.connect(os.path.join(self.db_path, 'market_data.db'))
        cursor = conn.cursor()
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS market_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            price REAL NOT NULL,
            price_change_percent REAL NOT NULL,
            volume REAL NOT NULL,
            quote_volume REAL NOT NULL,
            high_price REAL NOT NULL,
            low_price REAL NOT NULL,
            timestamp INTEGER NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_symbol_timestamp ON market_data(symbol, timestamp)')
        conn.commit()
        conn.close()

        # Create indicators.db
        conn = sqlite3.connect(os.path.join(self.db_path, 'indicators.db'))
        cursor = conn.cursor()
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS indicators (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            rsi_14 REAL DEFAULT NULL,
            macd REAL DEFAULT NULL,
            macd_signal REAL DEFAULT NULL,
            macd_histogram REAL DEFAULT NULL,
            ema_9 REAL DEFAULT NULL,
            ema_21 REAL DEFAULT NULL,
            volume_change_percent REAL DEFAULT NULL,
            timestamp INTEGER NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_symbol_timestamp ON indicators(symbol, timestamp)')
        conn.commit()
        conn.close()

        # Create signals.db
        conn = sqlite3.connect(os.path.join(self.db_path, 'signals.db'))
        cursor = conn.cursor()
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            signal_type TEXT NOT NULL CHECK(signal_type IN ('LONG', 'SHORT')),
            price REAL NOT NULL,
            confidence_score REAL NOT NULL,
            timestamp INTEGER NOT NULL,
            telegram_message_id INTEGER DEFAULT NULL,
            status TEXT NOT NULL CHECK(status IN ('SENT', 'CONFIRMED', 'REJECTED', 'COMPLETED')),
            exit_signal_id INTEGER DEFAULT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_symbol_date ON signals(symbol, date(created_at))')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_status ON signals(status)')
        conn.commit()
        conn.close()

        # Create positions.db
        conn = sqlite3.connect(os.path.join(self.db_path, 'positions.db'))
        cursor = conn.cursor()
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS positions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            position_type TEXT NOT NULL CHECK(position_type IN ('LONG', 'SHORT')),
            entry_price REAL NOT NULL,
            entry_time DATETIME NOT NULL,
            exit_price REAL DEFAULT NULL,
            exit_time DATETIME DEFAULT NULL,
            status TEXT NOT NULL CHECK(status IN ('OPEN', 'CLOSED')),
            profit_loss_percent REAL DEFAULT NULL,
            signal_id INTEGER NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_symbol ON positions(symbol)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_status ON positions(status)')
        conn.commit()
        conn.close()

        # Create ai_model.db
        conn = sqlite3.connect(os.path.join(self.db_path, 'ai_model.db'))
        cursor = conn.cursor()
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS model_features (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            price_change_1m REAL DEFAULT NULL,
            price_change_5m REAL DEFAULT NULL,
            price_change_15m REAL DEFAULT NULL,
            price_change_1h REAL DEFAULT NULL,
            volume_change_1m REAL DEFAULT NULL,
            volume_change_5m REAL DEFAULT NULL,
            rsi_value REAL DEFAULT NULL,
            macd_histogram REAL DEFAULT NULL,
            ema_crossover INTEGER DEFAULT NULL,
            timestamp INTEGER NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS model_predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            prediction_type TEXT NOT NULL CHECK(prediction_type IN ('LONG', 'SHORT', 'NEUTRAL')),
            confidence_score REAL NOT NULL,
            features_id INTEGER NOT NULL,
            actual_outcome TEXT DEFAULT NULL,
            accuracy REAL DEFAULT NULL,
            timestamp INTEGER NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (features_id) REFERENCES model_features(id)
        )
        ''')
        conn.commit()
        conn.close()

        # Create config.db
        conn = sqlite3.connect(os.path.join(self.db_path, 'config.db'))
        cursor = conn.cursor()
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS configuration (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            time_interval_minutes INTEGER DEFAULT 5,
            price_change_threshold REAL DEFAULT 3.0,
            max_signals_per_day INTEGER DEFAULT 3,
            telegram_token TEXT NOT NULL,
            telegram_chat_id TEXT NOT NULL,
            last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # Insert default configuration if it doesn't exist
        cursor.execute('SELECT COUNT(*) FROM configuration')
        if cursor.fetchone()[0] == 0:
            cursor.execute('''
            INSERT INTO configuration (
                time_interval_minutes, 
                price_change_threshold, 
                max_signals_per_day,
                telegram_token,
                telegram_chat_id,
                last_updated
            ) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (
                5,  # Default interval: 5 minutes
                3.0,  # Default threshold: 3%
                3,  # Default max signals: 3 per day
                os.getenv('TELEGRAM_TOKEN'),
                os.getenv('TELEGRAM_CHAT_ID')
            ))
        conn.commit()
        conn.close()

    def setup_background_tasks(self):
        """Setup background tasks for periodic operations"""
        self.background_tasks = [
            {
                'name': 'performance_evaluation',
                'interval': 6 * 3600,  # 6 hours
                'last_run': 0,
                'func': self.run_performance_evaluation
            },
            {
                'name': 'accuracy_tracking',
                'interval': 3600,  # 1 hour
                'last_run': 0,
                'func': self.run_accuracy_tracking
            },
            {
                'name': 'model_parameter_adjustment',
                'interval': 12 * 3600,  # 12 hours
                'last_run': 0,
                'func': self.run_model_parameter_adjustment
            }
        ]

    def run_background_tasks(self):
        """Run background tasks at their specified intervals"""
        current_time = time.time()

        for task in self.background_tasks:
            if current_time - task['last_run'] >= task['interval']:
                logger.info(f"Running background task: {task['name']}")
                try:
                    task['func']()
                    task['last_run'] = current_time
                except Exception as e:
                    logger.error(f"Error in background task {task['name']}: {e}")

    def run_performance_evaluation(self):
        """Run performance evaluation task"""
        try:
            report = self.performance_evaluator.evaluate_predictions()
            if report:
                # Send summary to Telegram
                overall_accuracy = report.get('overall_accuracy', 0)
                total_predictions = report.get('total_predictions', 0)

                message = f"""📊 *Performance Report*
                           Overall accuracy: {overall_accuracy:.2f}%
                           Total predictions analyzed: {total_predictions}
                           _Use /performance for detailed metrics_
                                                            """
                self.telegram_bot.send_message(message)
        except Exception as e:
            logger.error(f"Error in performance evaluation: {e}")

    def run_accuracy_tracking(self):
        """Run accuracy tracking task"""
        try:
            self.accuracy_tracker.track_prediction_outcomes()
        except Exception as e:
            logger.error(f"Error in accuracy tracking: {e}")

    def run_model_parameter_adjustment(self):
        """Run model parameter adjustment task"""
        try:
            self.accuracy_tracker.adjust_model_parameters()
        except Exception as e:
            logger.error(f"Error in model parameter adjustment: {e}")
    def handle_websocket_message(self, data):
        """Handle incoming WebSocket messages"""
        try:
            # Process each ticker in the data
            for ticker in data:
                if 'e' in ticker and ticker['e'] == '24hrTicker':
                    symbol = ticker['s']

                    # Only process perpetual futures (USDT pairs)
                    if symbol.endswith('USDT'):
                        ticker_data = {
                            'symbol': symbol,
                            'price': float(ticker['c']),
                            'volume': float(ticker['v']),
                            'timestamp': ticker['E']
                        }

                        # Update data processor
                        self.data_processor.update_data(ticker_data)

                        # Detect trend using the original data processor
                        trend_signal = self.data_processor.detect_trend(symbol)

                        # If a trend is detected, process it
                        if trend_signal:
                            # Process signal (send alert)
                            self.alert_system.process_signal(trend_signal)

                        # Check for exit signals for open positions
                        try:
                            open_positions = self.database.get_open_positions()
                            if open_positions:
                                for position in open_positions:
                                    position_data = {
                                        'symbol': position[1],
                                        'trend': position[3],
                                        'entry_price': position[2]
                                    }

                                    exit_signal = self.data_processor.detect_exit_signal(position_data)
                                    if exit_signal:
                                        self.alert_system.process_exit_signal(position[0], exit_signal)
                        except Exception as e:
                            logger.error(f"Error checking for exit signals: {e}")

            # Run background tasks if needed
            self.run_background_tasks()

        except Exception as e:
            logger.error(f"Error processing WebSocket message: {e}")
    async def start(self):
        """Start the Binance Futures Screener"""
        try:
            # The original TelegramBot doesn't have a start method, so we'll just log this
            logger.info("System is running. Press Ctrl+C to exit.")

            # Keep the main thread running
            while True:
                await asyncio.sleep(1)

        except KeyboardInterrupt:
            logger.info("Shutting down...")
        except Exception as e:
            logger.error(f"Error starting system: {e}")
        finally:
            # Cleanup
            if hasattr(self.websocket_client, 'close'):
                self.websocket_client.close()
            logger.info("System shutdown complete")


async def main():
    # Import enhanced components here to avoid circular imports
    from ai_model_enhanced import EnhancedAIModel
    from performance_evaluator import PerformanceEvaluator
    from confidence_scorer import AdvancedConfidenceScorer
    from accuracy_tracker import AccuracyTracker

    screener = EnhancedBinanceScreener()
    await screener.start()


if __name__ == "__main__":
    asyncio.run(main())