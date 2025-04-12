import logging
import os
import json
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import io
import telegram
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

logger = logging.getLogger(__name__)

class TelegramDashboard:
    def __init__(self, telegram_bot, db_path='data'):
        self.telegram_bot = telegram_bot
        self.db_path = db_path
        self.reports_dir = os.path.join(db_path, 'reports')
        os.makedirs(self.reports_dir, exist_ok=True)
        
        logger.info("Telegram dashboard initialized")
    
    async def setup_commands(self, application):
        """Set up command handlers for the dashboard"""
        application.add_handler(CommandHandler("dashboard", self.dashboard_command))
        application.add_handler(CommandHandler("performance", self.performance_command))
        application.add_handler(CommandHandler("positions", self.positions_command))
        application.add_handler(CommandHandler("signals", self.signals_command))
        application.add_handler(CommandHandler("settings", self.settings_command))
        application.add_handler(CallbackQueryHandler(self.button_callback))
        
        logger.info("Dashboard commands registered")
    
    async def dashboard_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Send main dashboard with overview of system status"""
        # Get system stats
        stats = self.get_system_stats()
        
        # Create dashboard message
        message = f"""📊 *BINANCE FUTURES SCREENER DASHBOARD*
                    🔍 *System Overview*
                    • Active since: {stats['active_since']}
                    • Uptime: {stats['uptime']}
                    • Database size: {stats['db_size']}

                    📈 *Trading Activity*
                    • Open positions: {stats['open_positions']}
                    • Signals today: {stats['signals_today']}
                    • Total signals: {stats['total_signals']}

                    🤖 *AI Performance*
                    • Overall accuracy: {stats['accuracy']:.2f}%
                    • Signals processed: {stats['signals_processed']}
                    • Learning cycles: {stats['learning_cycles']}

                    ⚙️ *Current Settings*
                    • Interval: {stats['interval']} minutes
                    • Threshold: {stats['threshold']}%
                    • Max signals: {stats['max_signals']}/day
                                            """
        
        # Create inline keyboard
        keyboard = [
            [
                InlineKeyboardButton("📊 Performance", callback_data="perf"),
                InlineKeyboardButton("📋 Positions", callback_data="pos")
            ],
            [
                InlineKeyboardButton("🔔 Recent Signals", callback_data="sig"),
                InlineKeyboardButton("⚙️ Settings", callback_data="set")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(message, reply_markup=reply_markup, parse_mode=telegram.constants.ParseMode.MARKDOWN)
    
    async def performance_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Send performance metrics and charts"""
        await update.message.reply_text("Generating performance report...")
        
        # Get performance data
        performance = self.get_performance_data()
        
        if not performance:
            await update.message.reply_text("No performance data available yet.")
            return
        
        # Create performance message
        message = f"""📊 *PERFORMANCE REPORT*

                    🎯 *Accuracy Metrics*
                    • Overall: {performance['overall_accuracy']:.2f}%
                    • LONG signals: {performance['long_accuracy']:.2f}%
                    • SHORT signals: {performance['short_accuracy']:.2f}%
                    • NEUTRAL signals: {performance['neutral_accuracy']:.2f}%

                    💰 *Profit Metrics*
                    • Average P/L: {performance['avg_pl']:.2f}%
                    • Best trade: {performance['best_trade']:.2f}%
                    • Worst trade: {performance['worst_trade']:.2f}%

                    🔝 *Top Performing Coins*
                                            """
        
        # Add top coins
        for symbol, acc in performance['top_symbols'].items():
            message += f"• {symbol}: {acc:.2f}%\n"
        
        # Generate and send accuracy chart
        plt.figure(figsize=(10, 6))
        
        labels = ['Overall', 'LONG', 'SHORT', 'NEUTRAL']
        values = [
            performance['overall_accuracy'],
            performance['long_accuracy'],
            performance['short_accuracy'],
            performance['neutral_accuracy']
        ]
        
        plt.bar(labels, values, color=['blue', 'green', 'red', 'gray'])
        plt.axhline(y=50, color='black', linestyle='--')
        plt.title('Signal Accuracy')
        plt.ylabel('Accuracy (%)')
        plt.ylim(0, 100)
        
        # Save chart to buffer
        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        buf.seek(0)
        
        # Send chart
        await update.message.reply_photo(buf)
        
        # Send performance message
        keyboard = [
            [
                InlineKeyboardButton("🔙 Back to Dashboard", callback_data="dash"),
                InlineKeyboardButton("📈 Detailed Report", callback_data="perf_detail")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(message, reply_markup=reply_markup, parse_mode=telegram.constants.ParseMode.MARKDOWN)
    
    async def positions_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Send current positions information"""
        # Get positions data
        positions = self.get_positions_data()
        
        if not positions:
            await update.message.reply_text("No open positions found.")
            return
        
        # Create positions message
        message = "📋 *CURRENT POSITIONS*\n\n"
        
        for pos in positions:
            entry_time = datetime.fromisoformat(pos['entry_time']).strftime("%Y-%m-%d %H:%M")
            duration = self.format_duration(pos['duration_seconds'])
            
            message += f"*{pos['symbol']}* - {'🟢 LONG' if pos['position_type'] == 'LONG' else '🔴 SHORT'}\n"
            message += f"• Entry: ${pos['entry_price']:.4f} ({entry_time})\n"
            message += f"• Current: ${pos['current_price']:.4f} ({pos['pl_percent']:.2f}%)\n"
            message += f"• Duration: {duration}\n"
            message += f"• ID: {pos['id']}\n\n"
        
        # Create inline keyboard
        keyboard = [
            [
                InlineKeyboardButton("🔙 Back to Dashboard", callback_data="dash"),
                InlineKeyboardButton("🔄 Refresh", callback_data="pos_refresh")
            ],
            [
                InlineKeyboardButton("❌ Close All", callback_data="pos_close_all")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(message, reply_markup=reply_markup, parse_mode=telegram.constants.ParseMode.MARKDOWN)
    
    async def signals_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Send recent signals information"""
        # Get recent signals
        signals = self.get_recent_signals()
        
        if not signals:
            await update.message.reply_text("No recent signals found.")
            return
        
        # Create signals message
        message = "🔔 *RECENT SIGNALS*\n\n"
        
        for signal in signals:
            signal_time = datetime.fromisoformat(signal['created_at']).strftime("%Y-%m-%d %H:%M")
            signal_type = "🟢 LONG" if signal['signal_type'] == 'LONG' else "🔴 SHORT"
            
            message += f"*{signal['symbol']}* - {signal_type}\n"
            message += f"• Price: ${signal['price']:.4f}\n"
            message += f"• Confidence: {signal['confidence_score']:.2f}\n"
            message += f"• Time: {signal_time}\n"
            message += f"• Status: {signal['status']}\n"
            message += f"• ID: {signal['id']}\n\n"
            
            if len(message) > 3000:  # Telegram message limit
                message += "... and more signals"
                break
        
        # Create inline keyboard
        keyboard = [
            [
                InlineKeyboardButton("🔙 Back to Dashboard", callback_data="dash"),
                InlineKeyboardButton("🔄 Refresh", callback_data="sig_refresh")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(message, reply_markup=reply_markup, parse_mode=telegram.constants.ParseMode.MARKDOWN)
    
    async def settings_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Send and manage system settings"""
        # Get current settings
        settings = self.get_system_settings()
        
        # Create settings message
        message = f"""⚙️ *SYSTEM SETTINGS*

                    • Time interval: {settings['time_interval_minutes']} minutes
                    • Price change threshold: {settings['price_change_threshold']}%
                    • Max signals per day: {settings['max_signals_per_day']}
                    • Last updated: {settings['last_updated']}

                    Use the buttons below to adjust settings or send commands like:
                    `/interval:10` - Set monitoring interval to 10 minutes
                    `/threshold:5` - Set price change threshold to 5%
                    `/maxsignals:3` - Set maximum signals per day to 3
                    """
        
        # Create inline keyboard
        keyboard = [
            [
                InlineKeyboardButton("⏱ Interval", callback_data="set_interval"),
                InlineKeyboardButton("📊 Threshold", callback_data="set_threshold")
            ],
            [
                InlineKeyboardButton("🔔 Max Signals", callback_data="set_maxsignals"),
                InlineKeyboardButton("🔙 Back", callback_data="dash")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(message, reply_markup=reply_markup, parse_mode=telegram.constants.ParseMode.MARKDOWN)
    
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button callbacks"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "dash":
            await self.dashboard_command(update, context)
        elif query.data == "perf":
            await self.performance_command(update, context)
        elif query.data == "pos":
            await self.positions_command(update, context)
        elif query.data == "sig":
            await self.signals_command(update, context)
        elif query.data == "set":
            await self.settings_command(update, context)
        elif query.data == "pos_refresh":
            await self.positions_command(update, context)
        elif query.data == "sig_refresh":
            await self.signals_command(update, context)
        elif query.data == "perf_detail":
            await self.send_detailed_performance(update, context)
        elif query.data == "pos_close_all":
            await self.close_all_positions(update, context)
        elif query.data.startswith("set_"):
            setting_type = query.data.split("_")[1]
            await self.handle_setting_change(update, context, setting_type)
    
    async def send_detailed_performance(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Send detailed performance report"""
        # Get performance data
        performance = self.get_performance_data(detailed=True)
        
        if not performance:
            await update.callback_query.message.reply_text("No detailed performance data available yet.")
            return
        
        # Send confusion matrix chart if available
        if 'confusion_matrix' in performance:
            # Generate confusion matrix chart
            plt.figure(figsize=(8, 6))
            
            labels = ['SHORT', 'NEUTRAL', 'LONG']
            matrix = performance['confusion_matrix']
            
            plt.imshow(matrix, cmap='Blues')
            plt.colorbar(label='Count')
            
            # Add labels
            plt.xticks(range(len(labels)), labels)
            plt.yticks(range(len(labels)), labels)
            plt.xlabel('Actual Outcome')
            plt.ylabel('Predicted Signal')
            plt.title('Confusion Matrix')
            
            # Add values to cells
            for i in range(len(labels)):
                for j in range(len(labels)):
                    plt.text(j, i, str(matrix[i][j]), 
                             ha='center', va='center', 
                             color='white' if matrix[i][j] > matrix.max()/2 else 'black')
            
            # Save chart to buffer
            buf = io.BytesIO()
            plt.savefig(buf, format='png')
            buf.seek(0)
            plt.close()
            
            # Send chart
            await update.callback_query.message.reply_photo(buf, caption="Confusion Matrix: Predicted vs Actual Outcomes")
        
        # Send performance over time chart
        if 'accuracy_over_time' in performance:
            plt.figure(figsize=(10, 6))
            
            dates = performance['accuracy_over_time']['dates']
            values = performance['accuracy_over_time']['values']
            
            plt.plot(dates, values, marker='o', linestyle='-', color='blue')
            plt.axhline(y=50, color='red', linestyle='--', label='50% Baseline')
            plt.title('Prediction Accuracy Over Time')
            plt.xlabel('Date')
            plt.ylabel('Accuracy (%)')
            plt.ylim(0, 100)
            plt.grid(True, linestyle='--', alpha=0.7)
            plt.xticks(rotation=45)
            plt.tight_layout()
            plt.legend()
            
            # Save chart to buffer
            buf = io.BytesIO()
            plt.savefig(buf, format='png')
            buf.seek(0)
            plt.close()
            
            # Send chart
            await update.callback_query.message.reply_photo(buf, caption="Prediction Accuracy Trend")
        
        # Create detailed message
        message = f"""📊 *DETAILED PERFORMANCE REPORT*

                    🎯 *Signal Distribution*
                    • Total signals: {performance['total_signals']}
                    • LONG signals: {performance['signal_counts']['LONG']} ({performance['signal_percentages']['LONG']:.1f}%)
                    • SHORT signals: {performance['signal_counts']['SHORT']} ({performance['signal_percentages']['SHORT']:.1f}%)
                    • NEUTRAL signals: {performance['signal_counts']['NEUTRAL']} ({performance['signal_percentages']['NEUTRAL']:.1f}%)

                    💰 *Profit Analysis*
                    • Profitable trades: {performance['profitable_percentage']:.1f}%
                    • Average holding time: {performance['avg_holding_time']}
                    • Risk/reward ratio: {performance['risk_reward_ratio']:.2f}

                    🧠 *AI Learning Progress*
                    • Initial accuracy: {performance['initial_accuracy']:.1f}%
                    • Current accuracy: {performance['current_accuracy']:.1f}%
                    • Improvement: {performance['accuracy_improvement']:.1f}%
                            """
        
        # Create inline keyboard
        keyboard = [
            [
                InlineKeyboardButton("🔙 Back to Performance", callback_data="perf"),
                InlineKeyboardButton("📊 Export Report", callback_data="export_report")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.callback_query.message.reply_text(message, reply_markup=reply_markup, parse_mode=telegram.constants.ParseMode.MARKDOWN)
    
    async def close_all_positions(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Close all open positions"""
        # Confirm action
        keyboard = [
            [
                InlineKeyboardButton("✅ Yes, close all", callback_data="confirm_close_all"),
                InlineKeyboardButton("❌ No, cancel", callback_data="pos")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.callback_query.message.reply_text(
            "Are you sure you want to close ALL open positions?",
            reply_markup=reply_markup
        )
    
    async def handle_setting_change(self, update: Update, context: ContextTypes.DEFAULT_TYPE, setting_type):
        """Handle setting change requests"""
        message = ""
        options = []
        
        if setting_type == "interval":
            message = "Select monitoring interval (minutes):"
            options = [1, 3, 5, 10, 15, 30, 60]
        elif setting_type == "threshold":
            message = "Select price change threshold (%):"
            options = [1.0, 2.0, 3.0, 5.0, 7.0, 10.0]
        elif setting_type == "maxsignals":
            message = "Select maximum signals per day:"
            options = [1, 2, 3, 5, 10, 20, 50]
        
        # Create keyboard with options
        keyboard = []
        row = []
        
        for i, option in enumerate(options):
            row.append(InlineKeyboardButton(str(option), callback_data=f"set_{setting_type}_{option}"))
            
            if (i + 1) % 3 == 0 or i == len(options) - 1:
                keyboard.append(row)
                row = []
        
        # Add back button
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="set")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.callback_query.message.reply_text(message, reply_markup=reply_markup)
    
    def get_system_stats(self):
        """Get system statistics for dashboard"""
        stats = {
            'active_since': 'Unknown',
            'uptime': 'Unknown',
            'db_size': 'Unknown',
            'open_positions': 0,
            'signals_today': 0,
            'total_signals': 0,
            'accuracy': 0.0,
            'signals_processed': 0,
            'learning_cycles': 0,
            'interval': 5,
            'threshold': 3.0,
            'max_signals': 3
        }
        
        try:
            # Get configuration
            conn = sqlite3.connect(os.path.join(self.db_path, 'config.db'))
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT time_interval_minutes, price_change_threshold, max_signals_per_day
            FROM configuration WHERE id = 1
            ''')
            
            row = cursor.fetchone()
            if row:
                stats['interval'] = row[0]
                stats['threshold'] = row[1]
                stats['max_signals'] = row[2]
            
            conn.close()
            
            # Get open positions count
            conn = sqlite3.connect(os.path.join(self.db_path, 'positions.db'))
            cursor = conn.cursor()
            
            cursor.execute('SELECT COUNT(*) FROM positions WHERE status = "OPEN"')
            stats['open_positions'] = cursor.fetchone()[0]
            
            conn.close()
            
            # Get signals count
            conn = sqlite3.connect(os.path.join(self.db_path, 'signals.db'))
            cursor = conn.cursor()
            
            # Today's signals
            today_start = datetime.combine(datetime.today(), datetime.min.time()).timestamp() * 1000
            cursor.execute('SELECT COUNT(*) FROM signals WHERE timestamp >= ?', (today_start,))
            stats['signals_today'] = cursor.fetchone()[0]
            
            # Total signals
            cursor.execute('SELECT COUNT(*) FROM signals')
            stats['total_signals'] = cursor.fetchone()[0]
            
            conn.close()
            
            # Get AI model stats
            conn = sqlite3.connect(os.path.join(self.db_path, 'ai_model.db'))
            cursor = conn.cursor()
            
            # Get accuracy
            cursor.execute('SELECT AVG(accuracy) FROM model_predictions WHERE accuracy IS NOT NULL')
            accuracy = cursor.fetchone()[0]
            if accuracy:
                stats['accuracy'] = accuracy * 100
            
            # Get signals processed
            cursor.execute('SELECT COUNT(*) FROM model_predictions')
            stats['signals_processed'] = cursor.fetchone()[0]
            
            # Get learning cycles (approximation based on model features)
            cursor.execute('SELECT COUNT(DISTINCT symbol) FROM model_features')
            symbols_count = cursor.fetchone()[0]
            
            cursor.execute('''
            SELECT COUNT(*) FROM model_features 
            GROUP BY symbol ORDER BY COUNT(*) DESC LIMIT 1
            ''')
            max_features = cursor.fetchone()
            if max_features:
                # Estimate learning cycles based on training frequency
                stats['learning_cycles'] = max_features[0] // 100 * symbols_count
            
            conn.close()
            
            # Calculate uptime and active since
            # Get earliest record timestamp
            conn = sqlite3.connect(os.path.join(self.db_path, 'market_data.db'))
            cursor = conn.cursor()
            
            cursor.execute('SELECT MIN(timestamp) FROM market_data')
            earliest_ts = cursor.fetchone()[0]
            
            if earliest_ts:
                start_time = datetime.fromtimestamp(earliest_ts / 1000)
                stats['active_since'] = start_time.strftime("%Y-%m-%d %H:%M")
                
                uptime_seconds = (datetime.now() - start_time).total_seconds()
                days, remainder = divmod(uptime_seconds, 86400)
                hours, remainder = divmod(remainder, 3600)
                minutes, _ = divmod(remainder, 60)
                
                stats['uptime'] = f"{int(days)}d {int(hours)}h {int(minutes)}m"
            
            conn.close()
            
            # Calculate database size
            total_size = 0
            for db_file in ['market_data.db', 'indicators.db', 'signals.db', 'positions.db', 'ai_model.db', 'config.db']:
                db_path = os.path.join(self.db_path, db_file)
                if os.path.exists(db_path):
                    total_size += os.path.getsize(db_path)
            
            # Convert to MB
            stats['db_size'] = f"{total_size / (1024 * 1024):.2f} MB"
            
        except Exception as e:
            logger.error(f"Error getting system stats: {e}")
        
        return stats
    
    def get_performance_data(self, detailed=False):
        """Get performance metrics for dashboard"""
        performance = {
            'overall_accuracy': 0.0,
            'long_accuracy': 0.0,
            'short_accuracy': 0.0,
            'neutral_accuracy': 0.0,
            'avg_pl': 0.0,
            'best_trade': 0.0,
            'worst_trade': 0.0,
            'top_symbols': {}
        }
        
        try:
            # Get prediction accuracy
            conn = sqlite3.connect(os.path.join(self.db_path, 'ai_model.db'))
            
            # Overall accuracy
            query = 'SELECT AVG(accuracy) * 100 FROM model_predictions WHERE accuracy IS NOT NULL'
            cursor = conn.cursor()
            cursor.execute(query)
            accuracy = cursor.fetchone()[0]
            if accuracy:
                performance['overall_accuracy'] = accuracy
            
            # Accuracy by prediction type
            for pred_type in ['LONG', 'SHORT', 'NEUTRAL']:
                query = '''
                SELECT AVG(accuracy) * 100 FROM model_predictions 
                WHERE prediction_type = ? AND accuracy IS NOT NULL
                '''
                cursor.execute(query, (pred_type,))
                type_accuracy = cursor.fetchone()[0]
                
                if type_accuracy:
                    performance[pred_type.lower() + '_accuracy'] = type_accuracy
            
            conn.close()
            
            # Get profit/loss metrics
            conn = sqlite3.connect(os.path.join(self.db_path, 'positions.db'))
            
            # Average P/L
            query = 'SELECT AVG(profit_loss_percent) FROM positions WHERE status = "CLOSED"'
            cursor = conn.cursor()
            cursor.execute(query)
            avg_pl = cursor.fetchone()[0]
            if avg_pl:
                performance['avg_pl'] = avg_pl
            
            # Best trade
            query = 'SELECT MAX(profit_loss_percent) FROM positions WHERE status = "CLOSED"'
            cursor.execute(query)
            best_trade = cursor.fetchone()[0]
            if best_trade:
                performance['best_trade'] = best_trade
            
            # Worst trade
            query = 'SELECT MIN(profit_loss_percent) FROM positions WHERE status = "CLOSED"'
            cursor.execute(query)
            worst_trade = cursor.fetchone()[0]
            if worst_trade:
                performance['worst_trade'] = worst_trade
            
            conn.close()
            
            # Get top performing symbols
            conn = sqlite3.connect(os.path.join(self.db_path, 'ai_model.db'))
            
            query = '''
            SELECT symbol, AVG(accuracy) * 100 as avg_accuracy
            FROM model_predictions
            WHERE accuracy IS NOT NULL
            GROUP BY symbol
            HAVING COUNT(*) >= 10
            ORDER BY avg_accuracy DESC
            LIMIT 5
            '''
            
            df = pd.read_sql_query(query, conn)
            conn.close()
            
            if not df.empty:
                performance['top_symbols'] = dict(zip(df['symbol'], df['avg_accuracy']))
            
            # Get detailed metrics if requested
            if detailed:
                # Signal distribution
                conn = sqlite3.connect(os.path.join(self.db_path, 'signals.db'))
                
                query = 'SELECT COUNT(*) FROM signals'
                cursor = conn.cursor()
                cursor.execute(query)
                total_signals = cursor.fetchone()[0]
                
                performance['total_signals'] = total_signals
                
                signal_counts = {}
                signal_percentages = {}
                
                for signal_type in ['LONG', 'SHORT', 'NEUTRAL']:
                    query = 'SELECT COUNT(*) FROM signals WHERE signal_type = ?'
                    cursor.execute(query, (signal_type,))
                    count = cursor.fetchone()[0]
                    
                    signal_counts[signal_type] = count
                    signal_percentages[signal_type] = (count / total_signals * 100) if total_signals > 0 else 0
                
                performance['signal_counts'] = signal_counts
                performance['signal_percentages'] = signal_percentages
                
                conn.close()
                
                # Profitable trades percentage
                conn = sqlite3.connect(os.path.join(self.db_path, 'positions.db'))
                
                query = '''
                SELECT COUNT(*) FROM positions 
                WHERE status = "CLOSED" AND profit_loss_percent > 0
                '''
                cursor = conn.cursor()
                cursor.execute(query)
                profitable_count = cursor.fetchone()[0]
                
                query = 'SELECT COUNT(*) FROM positions WHERE status = "CLOSED"'
                cursor.execute(query)
                closed_count = cursor.fetchone()[0]
                
                if closed_count > 0:
                    performance['profitable_percentage'] = (profitable_count / closed_count * 100)
                else:
                    performance['profitable_percentage'] = 0
                
                # Average holding time
                query = '''
                SELECT AVG((julianday(exit_time) - julianday(entry_time)) * 24 * 60)
                FROM positions WHERE status = "CLOSED"
                '''
                cursor.execute(query)
                avg_minutes = cursor.fetchone()[0]
                
                if avg_minutes:
                    hours, minutes = divmod(int(avg_minutes), 60)
                    performance['avg_holding_time'] = f"{hours}h {minutes}m"
                else:
                    performance['avg_holding_time'] = "N/A"
                
                # Risk/reward ratio
                query = '''
                SELECT ABS(AVG(profit_loss_percent) FILTER (WHERE profit_loss_percent > 0)) / 
                       ABS(AVG(profit_loss_percent) FILTER (WHERE profit_loss_percent < 0))
                FROM positions WHERE status = "CLOSED"
                '''
                cursor.execute(query)
                risk_reward = cursor.fetchone()[0]
                
                if risk_reward:
                    performance['risk_reward_ratio'] = risk_reward
                else:
                    performance['risk_reward_ratio'] = 0
                
                conn.close()
                
                # AI learning progress
                conn = sqlite3.connect(os.path.join(self.db_path, 'ai_model.db'))
                
                # Initial accuracy (first 100 predictions)
                query = '''
                SELECT AVG(accuracy) * 100 FROM model_predictions
                WHERE accuracy IS NOT NULL
                ORDER BY timestamp
                LIMIT 100
                '''
                cursor = conn.cursor()
                cursor.execute(query)
                initial_accuracy = cursor.fetchone()[0]
                
                # Current accuracy (last 100 predictions)
                query = '''
                SELECT AVG(accuracy) * 100 FROM model_predictions
                WHERE accuracy IS NOT NULL
                ORDER BY timestamp DESC
                LIMIT 100
                '''
                cursor.execute(query)
                current_accuracy = cursor.fetchone()[0]
                
                if initial_accuracy and current_accuracy:
                    performance['initial_accuracy'] = initial_accuracy
                    performance['current_accuracy'] = current_accuracy
                    performance['accuracy_improvement'] = current_accuracy - initial_accuracy
                else:
                    performance['initial_accuracy'] = 0
                    performance['current_accuracy'] = 0
                    performance['accuracy_improvement'] = 0
                
                # Confusion matrix
                query = '''
                SELECT prediction_type, actual_outcome, COUNT(*)
                FROM model_predictions
                WHERE accuracy IS NOT NULL AND actual_outcome IS NOT NULL
                GROUP BY prediction_type, actual_outcome
                '''
                
                cursor.execute(query)
                confusion_data = cursor.fetchall()
                
                if confusion_data:
                    # Initialize confusion matrix
                    labels = ['SHORT', 'NEUTRAL', 'LONG']
                    matrix = [[0, 0, 0], [0, 0, 0], [0, 0, 0]]
                    
                    # Fill matrix
                    for pred_type, actual, count in confusion_data:
                        pred_idx = labels.index(pred_type)
                        actual_idx = labels.index(actual)
                        matrix[pred_idx][actual_idx] = count
                    
                    performance['confusion_matrix'] = matrix
                
                # Accuracy over time
                query = '''
                SELECT date(datetime(timestamp/1000, 'unixepoch')) as date, 
                       AVG(accuracy) * 100 as daily_accuracy
                FROM model_predictions
                WHERE accuracy IS NOT NULL
                GROUP BY date
                ORDER BY date
                '''
                
                df = pd.read_sql_query(query, conn)
                
                if not df.empty:
                    performance['accuracy_over_time'] = {
                        'dates': df['date'].tolist(),
                        'values': df['daily_accuracy'].tolist()
                    }
                
                conn.close()
        
        except Exception as e:
            logger.error(f"Error getting performance data: {e}")
        
        return performance
    
    def get_positions_data(self):
        """Get current positions data"""
        positions = []
        
        try:
            conn = sqlite3.connect(os.path.join(self.db_path, 'positions.db'))
            
            query = '''
            SELECT id, symbol, position_type, entry_price, entry_time, signal_id
            FROM positions
            WHERE status = "OPEN"
            ORDER BY entry_time DESC
            '''
            
            cursor = conn.cursor()
            cursor.execute(query)
            open_positions = cursor.fetchall()
            
            conn.close()
            
            if not open_positions:
                return positions
            
            # Get current prices
            market_conn = sqlite3.connect(os.path.join(self.db_path, 'market_data.db'))
            market_cursor = market_conn.cursor()
            
            for pos_id, symbol, pos_type, entry_price, entry_time, signal_id in open_positions:
                # Get current price
                market_cursor.execute('''
                SELECT price FROM market_data
                WHERE symbol = ?
                ORDER BY timestamp DESC LIMIT 1
                ''', (symbol,))
                
                price_row = market_cursor.fetchone()
                
                if not price_row:
                    continue
                
                current_price = price_row[0]
                
                # Calculate P/L
                if pos_type == 'LONG':
                    pl_percent = ((current_price - entry_price) / entry_price) * 100
                else:  # SHORT
                    pl_percent = ((entry_price - current_price) / entry_price) * 100
                
                # Calculate duration
                entry_datetime = datetime.fromisoformat(entry_time)
                duration_seconds = (datetime.now() - entry_datetime).total_seconds()
                
                positions.append({
                    'id': pos_id,
                    'symbol': symbol,
                    'position_type': pos_type,
                    'entry_price': entry_price,
                    'entry_time': entry_time,
                    'current_price': current_price,
                    'pl_percent': pl_percent,
                    'duration_seconds': duration_seconds,
                    'signal_id': signal_id
                })
            
            market_conn.close()
        
        except Exception as e:
            logger.error(f"Error getting positions data: {e}")
        
        return positions
    
    def get_recent_signals(self, limit=10):
        """Get recent signals data"""
        signals = []
        
        try:
            conn = sqlite3.connect(os.path.join(self.db_path, 'signals.db'))
            
            query = '''
            SELECT id, symbol, signal_type, price, confidence_score, timestamp, status, created_at
            FROM signals
            ORDER BY timestamp DESC
            LIMIT ?
            '''
            
            cursor = conn.cursor()
            cursor.execute(query, (limit,))
            recent_signals = cursor.fetchall()
            
            conn.close()
            
            for signal_id, symbol, signal_type, price, confidence, timestamp, status, created_at in recent_signals:
                signals.append({
                    'id': signal_id,
                    'symbol': symbol,
                    'signal_type': signal_type,
                    'price': price,
                    'confidence_score': confidence,
                    'timestamp': timestamp,
                    'status': status,
                    'created_at': created_at
                })
        
        except Exception as e:
            logger.error(f"Error getting recent signals: {e}")
        
        return signals
    
    def get_system_settings(self):
        """Get current system settings"""
        settings = {
            'time_interval_minutes': 5,
            'price_change_threshold': 3.0,
            'max_signals_per_day': 3,
            'last_updated': 'Unknown'
        }
        
        try:
            conn = sqlite3.connect(os.path.join(self.db_path, 'config.db'))
            
            query = '''
            SELECT time_interval_minutes, price_change_threshold, max_signals_per_day, last_updated
            FROM configuration
            WHERE id = 1
            '''
            
            cursor = conn.cursor()
            cursor.execute(query)
            row = cursor.fetchone()
            
            conn.close()
            
            if row:
                settings['time_interval_minutes'] = row[0]
                settings['price_change_threshold'] = row[1]
                settings['max_signals_per_day'] = row[2]
                settings['last_updated'] = row[3]
        
        except Exception as e:
            logger.error(f"Error getting system settings: {e}")
        
        return settings
    
    def format_duration(self, seconds):
        """Format duration in seconds to a readable string"""
        hours, remainder = divmod(int(seconds), 3600)
        minutes, seconds = divmod(remainder, 60)
        
        if hours > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{minutes}m {seconds}s"
