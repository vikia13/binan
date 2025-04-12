import os
import logging
import argparse
from svr_model import SVRModel
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("svr_training.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("SVRTraining")

# Load environment variables
load_dotenv()

def main():
    parser = argparse.ArgumentParser(description='Train SVR models for price prediction')
    parser.add_argument('--symbols', type=str, help='Comma-separated list of symbols to train (e.g., BTCUSDT,ETHUSDT)')
    parser.add_argument('--all', action='store_true', help='Train models for all available symbols')

    args = parser.parse_args()

    # Initialize SVR model
    svr_model = SVRModel(db_path='data')

    if args.symbols:
        symbols = args.symbols.split(',')
        logger.info(f"Training SVR models for specified symbols: {symbols}")
        svr_model.batch_train(symbols)
    elif args.all:
        logger.info("Training SVR models for all available symbols")
        svr_model.batch_train()
    else:
        # Default to training models for major coins
        default_symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'XRPUSDT', 'ADAUSDT', 'SOLUSDT', 'DOGEUSDT']
        logger.info(f"Training SVR models for default symbols: {default_symbols}")
        svr_model.batch_train(default_symbols)

    logger.info("SVR model training completed")

if __name__ == "__main__":
    main()
