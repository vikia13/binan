import os
from dotenv import load_dotenv

# Print the current working directory
print(f"Current directory: {os.getcwd()}")

# Check if .env file exists
env_path = os.path.join(os.getcwd(), '.env')
print(f".env file exists: {os.path.exists(env_path)}")

# Load environment variables
print("Loading environment variables...")
load_dotenv(dotenv_path=env_path, override=True)

# Print all loaded environment variables
print("All environment variables:")
for key, value in os.environ.items():
    if key in ["TELEGRAM_TOKEN", "TELEGRAM_CHAT_ID"]:
        print(f"{key}: {value}")

# WebSocket configuration
BINANCE_WEBSOCKET_URL = "wss://fstream.binance.com/ws/!ticker@arr"

# Alert parameters
TIME_INTERVAL_MINUTES = 3
PRICE_CHANGE_THRESHOLD = 3.0
MAX_SIGNALS_PER_DAY = 50

# Risk management parameters
RISK_PER_TRADE = 0.03  # 3% of account balance
DEFAULT_ACCOUNT_BALANCE = 1000  # Default account balance in USDT
DEFAULT_LEVERAGE = 10  # Default leverage
STOP_LOSS_PERCENTAGE = 0.05  # 5% stop loss
TAKE_PROFIT_PERCENTAGE = 0.1  # 10% take profit
MAX_DRAWDOWN_PERCENTAGE = 0.05  # 5% maximum drawdown
TRAILING_STOP_ACTIVATION = 0.03  # Activate trailing stop after 3% profit
TRAILING_STOP_DISTANCE = 0.02  # 2% trailing stop distance

# Coin filtering parameters
MIN_PRICE_THRESHOLD = 0.50  # Minimum price for coins to be considered
EXCLUDED_SYMBOLS = [
    "BANANAUSDT",
    "SHIBAUSDT",
    "VINEUSDT",
    "DOGEUSDT",
    "BABYUSDT"
]  # Symbols to exclude

# Telegram configuration - Use direct access to environment variables
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# Print Telegram configuration values for debugging
if TELEGRAM_TOKEN:
    masked_token = TELEGRAM_TOKEN[:5] + "..." + TELEGRAM_TOKEN[-5:] if len(TELEGRAM_TOKEN) > 10 else "***"
    print(f"Using TELEGRAM_TOKEN: {masked_token}")
else:
    print("WARNING: TELEGRAM_TOKEN not found in environment variables")

if TELEGRAM_CHAT_ID:
    print(f"Using TELEGRAM_CHAT_ID: {TELEGRAM_CHAT_ID}")
else:
    print("WARNING: TELEGRAM_CHAT_ID not found in environment variables")

# Database configuration
DB_PATH = "positions.db"

# Technical indicators parameters
RSI_PERIOD = 14
RSI_OVERBOUGHT = 70
RSI_OVERSOLD = 30
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9
BOLLINGER_PERIOD = 20
BOLLINGER_STD = 2
EMA_50_PERIOD = 50
EMA_200_PERIOD = 200
ADX_PERIOD = 14
ADX_THRESHOLD = 25  # ADX above this indicates strong trend
STOCH_RSI_PERIOD = 14
STOCH_RSI_K = 3
STOCH_RSI_D = 3
STOCH_RSI_OVERBOUGHT = 80
STOCH_RSI_OVERSOLD = 20

# AI model parameters
AI_MODEL_PATH = "models/trend_detection_model.pkl"
AI_MEMORY_PATH = "data/ai_memory.json"
