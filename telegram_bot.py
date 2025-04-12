import telebot
import threading
import re
import sqlite3
import time
import logging
import os
import requests
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("telegram.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("TelegramBot")

# Load environment variables
load_dotenv()
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")


class TelegramBot:
    def __init__(self, database):
        self.token = TELEGRAM_TOKEN
        self.chat_id = TELEGRAM_CHAT_ID
        self.database = database
        self.bot = None
        self.thread = None
        self.running = True
        self.message_queue = []
        self.queue_lock = threading.RLock()
        self.reconnect_count = 0
        self.max_reconnect_delay = 300  # Maximum reconnect delay in seconds (5 minutes)
        self.last_update_id = 0  # Track the last update ID

        # Initialize bot
        self._init_bot()

        # Start message processing thread
        self.message_thread = threading.Thread(target=self._process_message_queue)
        self.message_thread.daemon = True
        self.message_thread.start()

        logger.info("Telegram bot initialized")

    def _init_bot(self):
        """Initialize the Telegram bot"""
        if not self.token:
            logger.warning("Telegram token is missing! Running in console-only mode.")
            return

        try:
            # First, clear any existing sessions
            self._clear_telegram_sessions()

            # Initialize the bot without starting polling
            self.bot = telebot.TeleBot(token=self.token)

            # Register handlers
            self._register_handlers()

            # Start manual update checking in a separate thread
            self.thread = threading.Thread(target=self._manual_updates_thread)
            self.thread.daemon = True
            self.thread.start()

            logger.info("Telegram bot started successfully")
        except Exception as e:
            logger.error(f"Error initializing Telegram bot: {e}")

    def _clear_telegram_sessions(self):
        """Clear any existing Telegram sessions"""
        try:
            # Delete any existing webhook
            logger.info("Clearing Telegram sessions...")
            delete_url = f"https://api.telegram.org/bot{self.token}/deleteWebhook"
            response = requests.get(delete_url)
            logger.info(f"Delete webhook response: {response.status_code}")

            # Make a getUpdates request with a timeout of 1 second and offset=-1
            # This will clear any existing getUpdates sessions
            updates_url = f"https://api.telegram.org/bot{self.token}/getUpdates?timeout=1&offset=-1"
            response = requests.get(updates_url)
            logger.info(f"getUpdates response: {response.status_code}")

            # Wait a moment for the changes to take effect
            time.sleep(2)
        except Exception as e:
            logger.error(f"Error clearing Telegram sessions: {e}")

    def _manual_updates_thread(self):
        """Thread function for manually checking for updates instead of using polling"""
        # Add a delay before starting to ensure previous sessions are terminated
        time.sleep(10)

        while self.running:
            try:
                self._check_for_updates()
                # Sleep for a short time between checks
                time.sleep(2)
            except Exception as e:
                if not self.running:
                    break

                logger.error(f"Error checking for Telegram updates: {e}")

                # Calculate reconnect delay with exponential backoff
                delay = min(2 ** self.reconnect_count, self.max_reconnect_delay)
                logger.info(f"Reconnecting Telegram bot in {delay} seconds...")
                time.sleep(delay)
                self.reconnect_count += 1

                # Try to clear sessions after errors
                if "Conflict: terminated by other getUpdates request" in str(e):
                    logger.info("Detected Telegram session conflict. Attempting to reset...")
                    self._clear_telegram_sessions()
                    time.sleep(30)  # Wait longer for the previous session to expire

    def _check_for_updates(self):
        """Manually check for updates using the Telegram API"""
        if not self.token:
            return

        try:
            # Use direct API call instead of bot.get_updates to avoid conflicts
            url = f"https://api.telegram.org/bot{self.token}/getUpdates"
            params = {
                'offset': self.last_update_id + 1,
                'timeout': 10
            }

            response = requests.get(url, params=params)
            if response.status_code == 200:
                data = response.json()
                if data['ok']:
                    updates = data['result']
                    if updates:
                        # Process each update
                        for update in updates:
                            # Update the last_update_id
                            if update['update_id'] > self.last_update_id:
                                self.last_update_id = update['update_id']

                            # Process the message
                            if 'message' in update:
                                message = update['message']
                                self._process_message(message)
        except Exception as e:
            logger.error(f"Error in check_for_updates: {e}")
            raise

    def _process_message(self, message):
        """Process a message from Telegram"""
        try:
            # Check if it's a command
            if 'text' in message and message['text'].startswith('/'):
                command_parts = message['text'].split()
                command = command_parts[0].lower()

                if command == '/start':
                    self._start_command_handler(message)
                elif command == '/help':
                    self._help_command_handler(message)
                elif command == '/status':
                    self._status_command_handler(message)
                elif command == '/close' and len(command_parts) > 1:
                    # Handle close command with position ID
                    try:
                        position_id = int(command_parts[1])
                        self._close_position_handler(message, position_id)
                    except ValueError:
                        self._send_reply(message, "❌ Invalid position ID. Use /close ID")
            # Handle regular messages
            elif 'text' in message:
                self._handle_message_handler(message)
        except Exception as e:
            logger.error(f"Error processing message: {e}")

    def _close_position_handler(self, message, position_id):
        """Handler for /close command to manually close a position"""
        try:
            # Get position details
            conn = sqlite3.connect(os.path.join(self.database.db_path, 'positions.db'))
            cursor = conn.cursor()
            cursor.execute('''
            SELECT symbol, position_type, entry_price
            FROM positions
            WHERE id = ? AND status = 'OPEN' AND confirmed = 1
            ''', (position_id,))

            position = cursor.fetchone()
            conn.close()

            if not position:
                self._send_reply(message, f"❌ No open position found with ID {position_id}")
                return

            symbol, position_type, entry_price = position

            # Get current price (you may need to adjust this based on your data source)
            # For now, we'll use a placeholder
            current_price = self._get_current_price(symbol)

            if not current_price:
                self._send_reply(message, f"❌ Could not get current price for {symbol}")
                return

            # Calculate profit/loss
            if position_type == 'LONG':
                profit_pct = ((current_price - entry_price) / entry_price) * 100
            else:  # SHORT
                profit_pct = ((entry_price - current_price) / entry_price) * 100

            # Create exit signal
            exit_signal = {
                'symbol': symbol,
                'exit_price': current_price,
                'profit_pct': profit_pct,
                'reason': 'Manual exit by user'
            }

            # Close the position
            from alert_system import AlertSystem
            alert_system = AlertSystem(self.database, self, None)
            if alert_system.process_exit_signal(position_id, exit_signal):
                self._send_reply(message, f"✅ Position {position_id} closed successfully")
            else:
                self._send_reply(message, f"❌ Failed to close position {position_id}")

        except Exception as e:
         logger.error(f"Error in close position handler: {e}")
        self._send_reply(message, "❌ Error closing position")

        def _get_current_price(self, symbol):
            """Get current price for a symbol"""
            try:
                # This is a placeholder - you should implement a proper way to get the current price
                # For example, by querying your database or making an API call to Binance
                import requests
                response = requests.get(f"https://fapi.binance.com/fapi/v1/ticker/price?symbol={symbol}")
                if response.status_code == 200:
                    data = response.json()
                    return float(data['price'])
                return None
            except Exception as e:
                logger.error(f"Error getting current price: {e}")
                return None

    def _process_message_queue(self):
            """Process queued messages with rate limiting"""
            while self.running:
                try:
                    # Check if there are messages to send
                    with self.queue_lock:
                        if not self.message_queue:
                            time.sleep(1)
                            continue

                        # Get the next message
                        message = self.message_queue.pop(0)

                    # Try to send the message
                    self._send_message_with_retry(message)

                    # Rate limiting to avoid Telegram API limits
                    time.sleep(1)

                except Exception as e:
                    logger.error(f"Error in message queue processing: {e}")
                    time.sleep(5)

    def _send_message_with_retry(self, message, max_retries=3):
            """Send a message with retry logic"""
            retries = 0
            while retries < max_retries:
                try:
                    if not self.token or not self.chat_id:
                        logger.info(f"[CONSOLE] {message}")
                        return True

                    # Use direct API call instead of bot.send_message
                    url = f"https://api.telegram.org/bot{self.token}/sendMessage"
                    params = {
                        'chat_id': self.chat_id,
                        'text': message,
                        'parse_mode': 'Markdown'
                    }

                    response = requests.post(url, json=params)
                    if response.status_code == 200:
                        self.reconnect_count = 0  # Reset reconnect count on success
                        return True
                    else:
                        logger.error(f"Error sending message: {response.status_code} - {response.text}")

                except Exception as e:
                    retries += 1
                    logger.error(f"Error sending Telegram message (attempt {retries}/{max_retries}): {e}")
                    if retries < max_retries:
                        time.sleep(3 * retries)  # Increasing delay between retries

            # If all retries failed, log the message locally
            logger.warning(f"Failed to send Telegram message after {max_retries} attempts. Message: {message}")
            return False

    def _register_handlers(self):
            """Register command and message handlers"""
            # This is now just a placeholder since we're handling messages manually
            pass

    def _start_command_handler(self, message):
            """Handler for /start command"""
            welcome_message = (
                "Welcome to Binance AI Futures Screener! 👋\n\n"
                "This bot monitors Binance Futures markets and sends alerts for potential trading opportunities.\n\n"
                "Commands:\n"
                "/help - Show available commands\n"
                "/status - Show current system status\n\n"
                "You can also respond to signals with:\n"
                "ID:ok - Confirm entry into a trade\n"
                "Symbol:X - Set maximum signals per day for a specific coin"
            )
            try:
                self._send_reply(message, welcome_message)
            except Exception as e:
                logger.error(f"Error in start command handler: {e}")

    def _help_command_handler(self, message):
            """Handler for /help command"""
            help_message = (
                "📈 Binance AI Futures Screener Commands 📉\n\n"
                "/start - Start the bot and see welcome message\n"
                "/help - Show this help message\n"
                "/status - Show current system status and active positions\n"
                "/close ID - Manually close a position by ID\n\n"
                "Signal Responses:\n"
                "ID:ok - Confirm you've taken a trade (e.g., '1:ok')\n"
                "Symbol:X - Limit signals for a specific coin (e.g., 'BTCUSDT:2')"
            )
            try:
                self._send_reply(message, help_message)
            except Exception as e:
                logger.error(f"Error in help command handler: {e}")

    def _status_command_handler(self, message):
            """Handler for /status command"""
            try:
                # Get open positions from database
                open_positions = self.database.get_open_positions()

                if not open_positions:
                    self._send_reply(message, "No active positions at the moment.")
                    return

                # Format positions
                positions_text = "🔍 Current Active Positions:\n\n"
                for position in open_positions:
                    position_id = position[0]  # position ID is the 1st column
                    symbol = position[1]  # symbol is the 2nd column
                    entry_price = position[2]  # entry_price is the 3rd column
                    trend = position[3]  # trend is the 4th column
                    entry_time = position[4]  # entry_time is the 5th column

                    trend_emoji = "🟢" if trend == "LONG" else "🔴"
                    positions_text += (
                        f"{trend_emoji} {symbol} (ID: {position_id})\n"
                        f"   Entry: ${entry_price:.4f} at {entry_time}\n\n"
                    )

                self._send_reply(message, positions_text)
            except Exception as e:
                logger.error(f"Error in status command handler: {e}")
                try:
                    self._send_reply(message, "Error retrieving positions. Please try again later.")
                except Exception:
                    pass

    def _handle_message_handler(self, message):
            """Handle user messages"""
            try:
                message_text = message['text']

                # Handle ID:ok format (trade confirmation)
                id_match = re.match(r'(\d+):ok', message_text)
                if id_match:
                    position_id = int(id_match.group(1))

                    # Mark the position as confirmed
                    if self.database.confirm_position(position_id):
                        position = self.database.get_position_by_signal_id(position_id)

                        if position:
                            self._send_reply(
                                message,
                                f"✅ Confirmed entry for signal ID {position_id} - {position[1]} {position[3]}\n"
                                f"Entry price: ${position[2]:.4f}"
                            )
                        else:
                            # Try to get position by ID
                            conn = sqlite3.connect(os.path.join(self.database.db_path, 'positions.db'))
                            cursor = conn.cursor()
                            cursor.execute('''
                                    SELECT id, symbol, entry_price, position_type
                                    FROM positions
                                    WHERE id = ?
                                    ''', (position_id,))

                            position = cursor.fetchone()
                            conn.close()

                            if position:
                                self._send_reply(
                                    message,
                                    f"✅ Confirmed entry for signal ID {position_id} - {position[1]} {position[3]}\n"
                                    f"Entry price: ${position[2]:.4f}"
                                )
                            else:
                                self._send_reply(message, f"❌ No signal found with ID {position_id}")
                    else:
                        self._send_reply(message, f"❌ Could not confirm position for signal ID {position_id}")

                    return

                # Handle Symbol:X format (max signals per day)
                signal_match = re.match(r'([A-Z0-9]+):(\d+)', message_text)
                if signal_match:
                    symbol = signal_match.group(1)
                    max_count = int(signal_match.group(2))

                    self.database.set_max_signals(symbol, max_count)
                    self._send_reply(
                        message,
                        f"✅ Set maximum signals for {symbol} to {max_count} per day"
                    )
                    return

                # Unknown message format
                self._send_reply(
                    message,
                    "I didn't understand that command. Try /help to see available commands."
                )
            except Exception as e:
                logger.error(f"Error handling message: {e}")

    def _send_reply(self, message, text):
            """Send a reply to a message"""
            try:
                chat_id = message['chat']['id']

                # Use direct API call
                url = f"https://api.telegram.org/bot{self.token}/sendMessage"
                params = {
                    'chat_id': chat_id,
                    'text': text,
                    'parse_mode': 'Markdown',
                    'reply_to_message_id': message['message_id']
                }

                response = requests.post(url, json=params)
                if response.status_code != 200:
                    logger.error(f"Error sending reply: {response.status_code} - {response.text}")
            except Exception as e:
                logger.error(f"Error sending reply: {e}")

    def send_message(self, message):
            """Queue a message to be sent to the configured chat ID"""
            with self.queue_lock:
                self.message_queue.append(message)

            # Also log to console for visibility
            logger.info(f"[TELEGRAM ALERT] {message}")
            return True

    def stop(self):
            """Stop the Telegram bot"""
            logger.info("Stopping Telegram bot...")
            self.running = False

            # Wait for threads to finish
            if self.thread and self.thread.is_alive():
                self.thread.join(timeout=2)

            if self.message_thread and self.message_thread.is_alive():
                self.message_thread.join(timeout=2)
