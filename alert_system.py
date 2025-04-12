import logging
import time

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("alerts.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("AlertSystem")


class AlertSystem:
    def __init__(self, database, telegram_bot, ai_model, position_manager=None, svr_model=None):
        self.database = database
        self.telegram_bot = telegram_bot
        self.ai_model = ai_model
        self.position_manager = position_manager
        self.svr_model = svr_model
        self.signal_counter = 0
        logger.info("Alert system initialized")

    def process_signal(self, signal):
        """Process a trading signal and send alerts if appropriate"""
        try:
            symbol = signal['symbol']
            trend = signal['trend']
            price = signal['price']

            # Check if we've already sent too many signals for this symbol today
            if not self.database.increment_signal_count(symbol):
                logger.info(f"Maximum daily signals reached for {symbol}, skipping")
                return False

            # Check with position manager if we should take this trade
            if self.position_manager and not self.position_manager.should_take_trade(symbol, trend):
                logger.info(f"Position manager rejected {symbol} {trend} signal")
                return False

            # If SVR model is available, validate the signal
            if self.svr_model:
                features_id = signal.get('features_id')
                if features_id:
                    svr_prediction, svr_confidence = self.svr_model.predict(symbol, features_id)

                    if svr_prediction != trend or svr_confidence < 0.6:
                        logger.info(
                            f"SVR model rejected {symbol} {trend} signal (predicted {svr_prediction} with {svr_confidence:.2f} confidence)"
                        )
                        return False

                    # Add SVR confidence to the signal
                    signal['svr_confidence'] = svr_confidence

            # Generate a unique signal ID
            self.signal_counter += 1
            signal_id = int(time.time()) % 10000 + self.signal_counter

            # Store the position in the database
            position_id = self.position_manager.add_position(symbol, price, trend,
                                                             signal_id) if self.position_manager else self.database.add_position(
                symbol, price, trend, signal_id)

            if position_id:
                # Format and send the alert message
                emoji = "🟢" if trend == "LONG" else "🔴"
                message = (f"{emoji} *{trend} Signal* - {symbol} #{position_id}\n\n"
                           f"Entry Price: ${price:.4f}\n")

                if 'rsi' in signal:
                    message += f"RSI: {signal.get('rsi', 'N/A'):.1f}\n"

                if 'macd_diff' in signal:
                    message += f"MACD: {signal.get('macd_diff', 'N/A'):.6f}\n"

                if 'svr_confidence' in signal:
                    message += f"SVR Confidence: {signal.get('svr_confidence', 'N/A'):.2f}\n"

                self.telegram_bot.send_message(message)
                logger.info(f"Signal alert sent for {symbol} {trend} at ${price:.4f}")
                return True
            else:
                logger.error(f"Failed to add position to database for {symbol}")
                return False

        except Exception as e:
            logger.error(f"Error processing signal: {e}")
            return False

    def process_exit_signal(self, position_id, exit_signal):
            """Process an exit signal for an open position"""
            try:
                symbol = exit_signal['symbol']
                exit_price = exit_signal['exit_price']
                profit_pct = exit_signal['profit_pct']
                reason = exit_signal.get('reason', 'Technical indicators')

                # Close the position using position manager if available
                if self.position_manager:
                    success = self.position_manager.close_position(position_id, exit_price, reason)
                else:
                    # Close the position in the database
                    success = self.database.close_position(position_id, exit_price)

                if success:
                    # Determine emoji based on profit/loss
                    if profit_pct > 0:
                        emoji = "✅"
                    else:
                        emoji = "❌"

                    # Format and send the exit alert
                    message = (
                        f"{emoji} *Exit Signal* - {symbol}\n\n"
                        f"Exit Price: ${exit_price:.4f}\n"
                        f"Profit/Loss: {profit_pct:.2f}%\n"
                        f"Reason: {reason}\n"
                    )

                    self.telegram_bot.send_message(message)
                    logger.info(f"Exit alert sent for {symbol} at ${exit_price:.4f} with {profit_pct:.2f}% P/L")
                    return True
                else:
                    logger.error(f"Failed to close position {position_id} in database")
                    return False

            except Exception as e:
                logger.error(f"Error processing exit signal: {e}")
                return False

    def send_weekly_report(self):
            """Send a weekly performance report"""
            try:
                if self.position_manager:
                    report = self.position_manager.generate_weekly_report()
                    self.telegram_bot.send_message(report)
                    logger.info("Sent weekly performance report")
                    return True
                else:
                    logger.warning("Position manager not available for weekly report")
                    return False
            except Exception as e:
                logger.error(f"Error sending weekly report: {e}")
                return False

    def send_performance_metrics(self, metrics):
            """Send performance metrics from AI model evaluation"""
            try:
                if not metrics:
                    return False

                message = f"📊 *AI Model Performance Update*\n\n"

                # Overall accuracy
                message += f"Overall Accuracy: {metrics.get('overall_accuracy', 0):.2f}%\n"
                message += f"Total Predictions: {metrics.get('total_predictions', 0)}\n\n"

                # Best performing symbols
                if 'best_symbols' in metrics and metrics['best_symbols']:
                    message += "*Top Performing Symbols:*\n"
                    for symbol in metrics['best_symbols'][:3]:  # Show top 3
                        message += f"- {symbol['symbol']}: {symbol['symbol_accuracy']:.2f}% ({symbol['prediction_count']} predictions)\n"
                    message += "\n"

                # Accuracy by prediction type
                if 'accuracy_by_type' in metrics and metrics['accuracy_by_type']:
                    message += "*Accuracy by Signal Type:*\n"
                    for type_data in metrics['accuracy_by_type']:
                        message += f"- {type_data['prediction_type']}: {type_data['type_accuracy']:.2f}%\n"
                    message += "\n"

                # Improvement trend
                if 'accuracy_improvement' in metrics:
                    if metrics['accuracy_improvement'] > 0:
                        message += f"📈 Model is improving: +{metrics['accuracy_improvement']:.2f}% accuracy\n"
                    elif metrics['accuracy_improvement'] < 0:
                        message += f"📉 Model is declining: {metrics['accuracy_improvement']:.2f}% accuracy\n"
                    else:
                        message += "Model accuracy is stable\n"

                self.telegram_bot.send_message(message)
                logger.info("Sent AI model performance metrics")
                return True

            except Exception as e:
                logger.error(f"Error sending performance metrics: {e}")
                return False
