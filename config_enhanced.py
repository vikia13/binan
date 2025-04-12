
import os
import json
import logging
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("config.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("Config")

# Load environment variables
load_dotenv()

# Default configuration values
DEFAULT_CONFIG = {
    # WebSocket configuration
    "BINANCE_WEBSOCKET_URL": "wss://fstream.binance.com/ws/!ticker@arr",

    # Alert parameters
    "TIME_INTERVAL_MINUTES": 3,
    "PRICE_CHANGE_THRESHOLD": 3.0,
    "MAX_SIGNALS_PER_DAY": 5,

    # Telegram configuration
    "TELEGRAM_TOKEN": os.environ.get("TELEGRAM_TOKEN", ""),
    "TELEGRAM_CHAT_ID": os.environ.get("TELEGRAM_CHAT_ID", ""),

    # Database configuration
    "DB_PATH": "data",

    # Technical indicators parameters
    "RSI_PERIOD": 14,
    "RSI_OVERBOUGHT": 70,
    "RSI_OVERSOLD": 30,
    "MACD_FAST": 12,
    "MACD_SLOW": 26,
    "MACD_SIGNAL": 9,
    "BOLLINGER_PERIOD": 20,
    "BOLLINGER_STD": 2,

    # AI model parameters
    "AI_MODEL_PATH": "models/trend_detection_model.pkl",

    # Risk management parameters
    "RISK_PER_TRADE": 0.02,  # 2% risk per trade
    "DEFAULT_ACCOUNT_BALANCE": 10000,  # $10,000 default account balance
    "DEFAULT_LEVERAGE": 5,  # 5x leverage
    "STOP_LOSS_PERCENTAGE": 0.05,  # 5% stop loss
    "TAKE_PROFIT_PERCENTAGE": 0.15,  # 15% take profit
    "TRAILING_STOP_ACTIVATION": 0.05,  # Activate trailing stop at 5% profit
    "TRAILING_STOP_DISTANCE": 0.02,  # 2% trailing stop distance
    "MAX_DRAWDOWN_PERCENTAGE": 0.15,  # 15% maximum drawdown
    "MIN_PRICE_THRESHOLD": 10,  # Minimum price threshold ($10)

    # Excluded symbols
    "EXCLUDED_SYMBOLS": ["BTCDOMUSDT", "DEFIUSDT"]
}

class ConfigManager:
    def __init__(self, config_file="config.json"):
        self.config_file = os.path.join("data", config_file)
        self.config = DEFAULT_CONFIG.copy()

        # Create data directory if it doesn't exist
        os.makedirs("data", exist_ok=True)

        # Load configuration from file if it exists
        self.load_config()

        # Log configuration
        logger.info("Configuration loaded")

    def load_config(self):
        """Load configuration from file"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    loaded_config = json.load(f)

                    # Update config with loaded values
                    for key, value in loaded_config.items():
                        self.config[key] = value

                logger.info(f"Loaded configuration from {self.config_file}")
            else:
                # Save default configuration
                self.save_config()
                logger.info("Created default configuration file")
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")

    def save_config(self):
        """Save configuration to file"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=4)
            logger.info(f"Saved configuration to {self.config_file}")
        except Exception as e:
            logger.error(f"Error saving configuration: {e}")

    def get(self, key, default=None):
        """Get a configuration value"""
        return self.config.get(key, default)

    def set(self, key, value):
        """Set a configuration value"""
        self.config[key] = value
        self.save_config()
        logger.info(f"Updated configuration: {key} = {value}")

    def update(self, config_dict):
        """Update multiple configuration values"""
        for key, value in config_dict.items():
            self.config[key] = value
        self.save_config()
        logger.info(f"Updated {len(config_dict)} configuration values")

    def get_all(self):
        """Get all configuration values"""
        return self.config.copy()

    def reset_to_defaults(self):
        """Reset configuration to default values"""
        self.config = DEFAULT_CONFIG.copy()
        self.save_config()
        logger.info("Reset configuration to default values")

# Create a global instance of the config manager
config_manager = ConfigManager()

# Export all configuration values as module variables
for key, value in config_manager.get_all().items():
    globals()[key] = value

def update_config(key, value):
    """Update a configuration value and update the module variable"""
    config_manager.set(key, value)
    globals()[key] = value
