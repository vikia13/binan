import os
import time
import signal
import logging
from dotenv import load_dotenv
from database import Database
from telegram_bot import TelegramBot
from data_processor_simple import DataProcessor
from ai_model_simple import SimpleTrendDetectionModel
from alert_system import AlertSystem
from websocket_client import WebSocketClient
from simple_alert import SimpleAlert

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("app_simple.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("Main")

# Load environment variables
load_dotenv()

# Global variables
running = True
components = []
data_processor = None
alert_system = None

def signal_handler(_, __):
    """Handle termination signals"""
    global running
    logger.info("Received termination signal. Shutting down...")
    running = False

def handle_websocket_message(data):
    """Process incoming WebSocket messages"""
    global data_processor, alert_system

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
                    data_processor.update_data(ticker_data)

                    # Detect trend
                    trend_signal = data_processor.detect_trend(symbol)
                    if trend_signal and alert_system:
                        # Process signal
                        alert_system.process_signal(trend_signal)

                        # Check for exit signals for open positions
                        for position in database.get_open_positions():
                            position_data = {
                                'symbol': position[1],
                                'trend': position[3],
                                'entry_price': position[2]
                            }

                            exit_signal = data_processor.detect_exit_signal(position_data)
                            if exit_signal:
                                alert_system.process_exit_signal(position[0], exit_signal)
    except Exception as e:
        logger.error(f"Error processing WebSocket message: {e}")

def main():
    global running, components, data_processor, alert_system, database

    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        # Initialize database
        logger.info("Initializing database...")
        database = Database()
        components.append(database)

        # Initialize data processor
        logger.info("Initializing data processor...")
        data_processor = DataProcessor()

        # Check if Telegram token is available
        telegram_token = os.environ.get("TELEGRAM_TOKEN")
        if telegram_token:
            # Initialize Telegram bot
            logger.info("Starting Telegram bot...")
            telegram_bot = TelegramBot(database)
            components.append(telegram_bot)

            # Initialize AI model
            logger.info("Initializing AI model...")
            ai_model = SimpleTrendDetectionModel(data_processor)
            components.append(ai_model)

            # Initialize alert system with Telegram
            logger.info("Setting up alert system with Telegram...")
            alert_system = AlertSystem(database, telegram_bot, ai_model)
        else:
            # Use simple alert system without Telegram
            logger.info("No Telegram token found, using simple alert system...")
            simple_alert = SimpleAlert()
            components.append(simple_alert)

            # Initialize alert system with simple alerts
            logger.info("Setting up alert system with simple alerts...")
            alert_system = AlertSystem(database, simple_alert, None)

        # Connect to Binance WebSocket
        logger.info("Connecting to Binance WebSocket...")
        websocket_url = "wss://fstream.binance.com/ws/!ticker@arr"
        ws_client = WebSocketClient(websocket_url, handle_websocket_message)
        components.append(ws_client)

        logger.info("System is running. Press Ctrl+C to exit.")

        # Main loop
        while running:
            time.sleep(1)

    except Exception as e:
        logger.error(f"Error in main application: {e}")
    finally:
        cleanup()

def cleanup():
    """Clean up resources before exiting"""
    logger.info("Cleaning up resources...")

    for component in reversed(components):
        try:
            if hasattr(component, 'close'):
                component.close()
            elif hasattr(component, 'stop'):
                component.stop()
        except Exception as e:
            logger.error(f"Error cleaning up component: {e}")

    logger.info("Shutdown complete")

if __name__ == "__main__":
    main()
