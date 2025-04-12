import logging
import inspect
from alert_system import AlertSystem as OriginalAlertSystem
from ai_model import AIModelWrapper

logger = logging.getLogger(__name__)

class EnhancedAlertSystem:
    def __init__(self, telegram_bot, ai_model, confidence_scorer=None):
        """Adapter for the original AlertSystem class"""
        # Get the original telegram_bot if we're using our adapter
        if hasattr(telegram_bot, 'original_bot'):
            telegram_bot_to_use = telegram_bot.original_bot
        else:
            telegram_bot_to_use = telegram_bot

        # Create an instance of the original AIModelWrapper
        original_ai_model = AIModelWrapper()

        # Initialize with the appropriate parameters
        self.original_alert_system = OriginalAlertSystem(telegram_bot_to_use, original_ai_model)

        self.confidence_scorer = confidence_scorer
        logger.info("Enhanced alert system adapter initialized")

    def process_signal(self, signal):
        """Process a signal using the original alert system"""
        return self.original_alert_system.process_signal(signal)

    def process_exit_signal(self, position_id, exit_signal):
        """Process an exit signal using the original alert system"""
        if hasattr(self.original_alert_system, 'process_exit_signal'):
            return self.original_alert_system.process_exit_signal(position_id, exit_signal)
        return None