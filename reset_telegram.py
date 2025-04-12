import requests
import os
import time
from dotenv import load_dotenv
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("telegram_reset.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("TelegramReset")

# Load environment variables
load_dotenv()
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")


def reset_telegram_session():
    """Reset any existing Telegram webhook and getUpdates sessions"""
    if not TELEGRAM_TOKEN:
        logger.error("No Telegram token found in environment variables")
        return False

    try:
        # First, delete any existing webhook
        logger.info("Deleting any existing Telegram webhook...")
        delete_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/deleteWebhook?drop_pending_updates=true"
        response = requests.get(delete_url)
        logger.info(f"Delete webhook response: {response.status_code} - {response.text}")

        # Then, make multiple getUpdates requests with increasing offset
        # This will clear any existing getUpdates sessions and pending updates
        logger.info("Clearing existing getUpdates sessions...")

        # First request with offset=-1 to get the latest update ID
        updates_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates?timeout=1&offset=-1"
        response = requests.get(updates_url)
        logger.info(f"Initial getUpdates response: {response.status_code}")

        # If we got updates, get the latest update_id and clear everything after it
        if response.status_code == 200:
            data = response.json()
            if data.get('ok') and data.get('result'):
                latest_update_id = data['result'][-1]['update_id']
                logger.info(f"Latest update ID: {latest_update_id}")

                # Clear all updates by setting offset to latest_update_id + 1
                clear_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates?offset={latest_update_id + 1}"
                response = requests.get(clear_url)
                logger.info(f"Clear updates response: {response.status_code} - {response.text}")

        # Wait for changes to take effect
        logger.info("Waiting for Telegram API to process changes...")
        time.sleep(5)

        return True
    except Exception as e:
        logger.error(f"Error resetting Telegram session: {e}")
        return False


if __name__ == "__main__":
    logger.info("Starting Telegram session reset...")
    reset_telegram_session()
    logger.info("Telegram session reset completed")
