import logging
from telegram_bot import TelegramBot as OriginalTelegramBot

logger = logging.getLogger(__name__)


class EnhancedTelegramBot:
    def __init__(self, token, chat_id):
        """Adapter for the original TelegramBot class"""
        # Your original TelegramBot expects a database parameter
        from database_adapter import DatabaseAdapter
        database = DatabaseAdapter('data')

        self.original_bot = OriginalTelegramBot(database)
        self.chat_id = chat_id
        logger.info("Enhanced Telegram bot adapter initialized")

    async def start(self):
        """Start the Telegram bot - this is a no-op since the original bot doesn't have a start method"""
        # This is just a placeholder since the original bot doesn't have a start method
        pass

    def send_message(self, message):
        """Send a message using the original bot"""
        return self.original_bot.send_message(message)

    def process_command(self, command_text):
        """Process a command using the original bot"""
        if hasattr(self.original_bot, 'process_command'):
            return self.original_bot.process_command(command_text)
        return None

    def handle_message(self, update, context):
        """Handle a message using the original bot"""
        if hasattr(self.original_bot, 'handle_message'):
            return self.original_bot.handle_message(update, context)
        return None

    def handle_command(self, update, context):
        """Handle a command using the original bot"""
        if hasattr(self.original_bot, 'handle_command'):
            return self.original_bot.handle_command(update, context)
        return None

    def send_signal(self, message):
        """Send a signal using the original bot"""
        if hasattr(self.original_bot, 'send_signal'):
            return self.original_bot.send_signal(message)
        return self.send_message(message)

    @property
    def application(self):
        """Get the application from the original bot"""
        if hasattr(self.original_bot, 'application'):
            return self.original_bot.application
        return None
