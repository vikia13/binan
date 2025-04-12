import logging
import os
import sqlite3
import json
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Default risk management settings
RISK_PER_TRADE = 0.02  # 2% risk per trade
DEFAULT_ACCOUNT_BALANCE = 10000  # $10,000 default account balance
DEFAULT_LEVERAGE = 5  # 5x leverage
STOP_LOSS_PERCENTAGE = 0.05  # 5% stop loss
TAKE_PROFIT_PERCENTAGE = 0.15  # 15% take profit
TRAILING_STOP_ACTIVATION = 0.05  # Activate trailing stop at 5% profit
TRAILING_STOP_DISTANCE = 0.02  # 2% trailing stop distance
MAX_DRAWDOWN_PERCENTAGE = 0.15  # 15% maximum drawdown
MAX_SIGNALS_PER_DAY = 5  # Maximum 5 signals per day per symbol
MIN_PRICE_THRESHOLD = 10  # Minimum price threshold ($10)
EXCLUDED_SYMBOLS = []  # Symbols to exclude


class PositionManager:
    def __init__(self, db_path='data'):
        self.db_path = db_path
        os.makedirs(db_path, exist_ok=True)

        # Initialize active positions dictionary
        self.active_positions = {}

        # Initialize AI memory for learning from past trades
        self.ai_memory = {}

        # Load active positions from database
        self._load_active_positions()

        # Load AI memory from file
        self._load_ai_memory()

        logger.info("Position manager initialized")

    def _load_active_positions(self):
        """Load active positions from database"""
        try:
            conn = sqlite3.connect(os.path.join(self.db_path, 'positions.db'))
            cursor = conn.cursor()

            cursor.execute('''
            SELECT id, symbol, entry_price, position_type, entry_time, signal_id
            FROM positions
            WHERE status = 'OPEN' AND confirmed = 1
            ''')

            positions = cursor.fetchall()
            conn.close()

            for position in positions:
                position_id, symbol, entry_price, direction, entry_time, signal_id = position

                # Calculate stop loss and take profit
                if direction == 'LONG':
                    stop_loss = entry_price * (1 - STOP_LOSS_PERCENTAGE)
                    take_profit = entry_price * (1 + TAKE_PROFIT_PERCENTAGE)
                else:  # SHORT
                    stop_loss = entry_price * (1 + STOP_LOSS_PERCENTAGE)
                    take_profit = entry_price * (1 - TAKE_PROFIT_PERCENTAGE)

                # Add to active positions
                self.active_positions[symbol] = {
                    'id': position_id,
                    'symbol': symbol,
                    'direction': direction,
                    'entry_price': entry_price,
                    'entry_time': entry_time,
                    'signal_id': signal_id,
                    'stop_loss': stop_loss,
                    'take_profit': take_profit,
                    'highest_price': entry_price,
                    'lowest_price': entry_price,
                    'trailing_stop_active': False
                }

            logger.info(f"Loaded {len(positions)} active positions from database")
        except Exception as e:
            logger.error(f"Error loading active positions: {e}")

    def _load_ai_memory(self):
        """Load AI memory from file"""
        memory_file = os.path.join(self.db_path, 'ai_memory.json')

        if os.path.exists(memory_file):
            try:
                with open(memory_file, 'r') as f:
                    self.ai_memory = json.load(f)
                logger.info(f"Loaded AI memory with {len(self.ai_memory)} symbols")
            except Exception as e:
                logger.error(f"Error loading AI memory: {e}")
                self._initialize_ai_memory()
        else:
            self._initialize_ai_memory()

    def _initialize_ai_memory(self):
        """Initialize AI memory structure"""
        self.ai_memory = {}
        self._save_ai_memory()

    def _save_ai_memory(self):
        """Save AI memory to file"""
        memory_file = os.path.join(self.db_path, 'ai_memory.json')

        try:
            with open(memory_file, 'w') as f:
                json.dump(self.ai_memory, f, indent=4)
            logger.debug("Saved AI memory")
        except Exception as e:
            logger.error(f"Error saving AI memory: {e}")

    def has_active_position(self, symbol):
        """Check if there's an active position for a symbol"""
        return symbol in self.active_positions

    def add_position(self, symbol, entry_price, direction, signal_id):
        """Add a new position"""
        try:
            # Check if we already have a position for this symbol
            if symbol in self.active_positions:
                logger.warning(f"Already have an active position for {symbol}")
                return None

            # Calculate stop loss and take profit
            if direction == 'LONG':
                stop_loss = entry_price * (1 - STOP_LOSS_PERCENTAGE)
                take_profit = entry_price * (1 + TAKE_PROFIT_PERCENTAGE)
            else:  # SHORT
                stop_loss = entry_price * (1 + STOP_LOSS_PERCENTAGE)
                take_profit = entry_price * (1 - TAKE_PROFIT_PERCENTAGE)

            # Add to database
            conn = sqlite3.connect(os.path.join(self.db_path, 'positions.db'))
            cursor = conn.cursor()

            # Insert position
            cursor.execute('''
            INSERT INTO positions (
                symbol, position_type, entry_price, entry_time, status, confirmed, signal_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                symbol,
                direction,
                entry_price,
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'OPEN',
                0,  # Not confirmed by default
                signal_id
            ))

            conn.commit()
            cursor.execute('SELECT last_insert_rowid()')
            position_id = cursor.fetchone()[0]
            conn.close()

            # Add to active positions
            self.active_positions[symbol] = {
                'id': position_id,
                'symbol': symbol,
                'direction': direction,
                'entry_price': entry_price,
                'entry_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'signal_id': signal_id,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'highest_price': entry_price,
                'lowest_price': entry_price,
                'trailing_stop_active': False
            }

            logger.info(f"Added new position for {symbol} {direction} at ${entry_price:.4f}")
            return position_id
        except Exception as e:
            logger.error(f"Error adding position: {e}")
            return None

    def confirm_position(self, position_id):
        """Confirm a position"""
        try:
            # Find the position in active positions
            for symbol, position in self.active_positions.items():
                if position['id'] == position_id:
                    # Update database
                    conn = sqlite3.connect(os.path.join(self.db_path, 'positions.db'))
                    cursor = conn.cursor()

                    cursor.execute('''
                    UPDATE positions
                    SET confirmed = 1
                    WHERE id = ?
                    ''', (position_id,))

                    conn.commit()
                    rows_affected = cursor.rowcount
                    conn.close()

                    if rows_affected > 0:
                        logger.info(f"Confirmed position {position_id} for {symbol}")
                        return True

            # If not found in active positions, try to find in database
            conn = sqlite3.connect(os.path.join(self.db_path, 'positions.db'))
            cursor = conn.cursor()

            cursor.execute('''
            SELECT id, symbol, entry_price, position_type, entry_time, signal_id
            FROM positions
            WHERE id = ? OR signal_id = ?
            ''', (position_id, position_id))

            position = cursor.fetchone()

            if position:
                position_id, symbol, entry_price, direction, entry_time, signal_id = position

                # Update database
                cursor.execute('''
                UPDATE positions
                SET confirmed = 1
                WHERE id = ?
                ''', (position_id,))

                conn.commit()
                rows_affected = cursor.rowcount

                if rows_affected > 0:
                    # Calculate stop loss and take profit
                    if direction == 'LONG':
                        stop_loss = entry_price * (1 - STOP_LOSS_PERCENTAGE)
                        take_profit = entry_price * (1 + TAKE_PROFIT_PERCENTAGE)
                    else:  # SHORT
                        stop_loss = entry_price * (1 + STOP_LOSS_PERCENTAGE)
                        take_profit = entry_price * (1 - TAKE_PROFIT_PERCENTAGE)

                    # Add to active positions
                    self.active_positions[symbol] = {
                        'id': position_id,
                        'symbol': symbol,
                        'direction': direction,
                        'entry_price': entry_price,
                        'entry_time': entry_time,
                        'signal_id': signal_id,
                        'stop_loss': stop_loss,
                        'take_profit': take_profit,
                        'highest_price': entry_price,
                        'lowest_price': entry_price,
                        'trailing_stop_active': False
                    }

                    logger.info(f"Confirmed position {position_id} for {symbol}")
                    conn.close()
                    return True

            conn.close()
            return False
        except Exception as e:
            logger.error(f"Error confirming position: {e}")
            return False

    def close_position(self, position_id, exit_price, reason="Manual exit"):
        """Close a position"""
        try:
            # Find the position in active positions
            symbol_to_remove = None
            position_data = None

            for symbol, position in self.active_positions.items():
                if position['id'] == position_id:
                    symbol_to_remove = symbol
                    position_data = position
                    break

            if not position_data:
                logger.warning(f"No active position found with ID {position_id}")
                return False

            # Calculate profit/loss
            entry_price = position_data['entry_price']
            direction = position_data['direction']

            if direction == 'LONG':
                profit_pct = ((exit_price - entry_price) / entry_price) * 100
            else:  # SHORT
                profit_pct = ((entry_price - exit_price) / entry_price) * 100

            # Update database
            conn = sqlite3.connect(os.path.join(self.db_path, 'positions.db'))
            cursor = conn.cursor()

            cursor.execute('''
            UPDATE positions SET 
                exit_price = ?, 
                exit_time = ?,
                status = 'CLOSED',
                profit_loss_percent = ?,
                exit_reason = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            ''', (
                exit_price,
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                profit_pct,
                reason,
                position_id
            ))

            conn.commit()
            rows_affected = cursor.rowcount
            conn.close()

            if rows_affected > 0:
                # Update AI memory with trade result
                self._update_ai_memory(symbol_to_remove, direction, profit_pct)

                # Remove from active positions
                if symbol_to_remove in self.active_positions:
                    del self.active_positions[symbol_to_remove]

                logger.info(f"Closed position {position_id} for {symbol_to_remove} with P/L: {profit_pct:.2f}%")
                return True

            return False
        except Exception as e:
            logger.error(f"Error closing position: {e}")
            return False

    def update_price_data(self, symbol, current_price):
        """Update price data for a symbol with active position"""
        if symbol not in self.active_positions:
            return

        position = self.active_positions[symbol]
        direction = position['direction']

        # Update highest and lowest prices
        if current_price > position['highest_price']:
            position['highest_price'] = current_price

        if current_price < position['lowest_price']:
            position['lowest_price'] = current_price

        # Check if trailing stop should be activated
        if not position['trailing_stop_active']:
            if direction == 'LONG':
                profit_pct = ((current_price - position['entry_price']) / position['entry_price']) * 100
                if profit_pct >= TRAILING_STOP_ACTIVATION * 100:
                    position['trailing_stop_active'] = True
                    logger.info(f"Activated trailing stop for {symbol} at {profit_pct:.2f}% profit")
            else:  # SHORT
                profit_pct = ((position['entry_price'] - current_price) / position['entry_price']) * 100
                if profit_pct >= TRAILING_STOP_ACTIVATION * 100:
                    position['trailing_stop_active'] = True
                    logger.info(f"Activated trailing stop for {symbol} at {profit_pct:.2f}% profit")

        # Update trailing stop if active
        if position['trailing_stop_active']:
            if direction == 'LONG':
                new_stop = current_price * (1 - TRAILING_STOP_DISTANCE)
                if new_stop > position['stop_loss']:
                    position['stop_loss'] = new_stop
            else:  # SHORT
                new_stop = current_price * (1 + TRAILING_STOP_DISTANCE)
                if new_stop < position['stop_loss']:
                    position['stop_loss'] = new_stop

    def check_exit_conditions(self, symbol, current_price, indicators=None):
        """Check if exit conditions are met for a position"""
        if symbol not in self.active_positions:
            return None

        position = self.active_positions[symbol]
        direction = position['direction']
        entry_price = position['entry_price']
        stop_loss = position['stop_loss']
        take_profit = position['take_profit']

        # Calculate current profit/loss
        if direction == 'LONG':
            profit_pct = ((current_price - entry_price) / entry_price) * 100

            # Check stop loss
            if current_price <= stop_loss:
                return {
                    'position_id': position['id'],
                    'symbol': symbol,
                    'exit_price': current_price,
                    'profit_pct': profit_pct,
                    'reason': 'Stop loss triggered'
                }

            # Check take profit
            if current_price >= take_profit:
                return {
                    'position_id': position['id'],
                    'symbol': symbol,
                    'exit_price': current_price,
                    'profit_pct': profit_pct,
                    'reason': 'Take profit reached'
                }

            # Check technical indicators if provided
            if indicators:
                # Exit on strong bearish signals
                if (indicators.get('macd_diff', 0) < -0.0002 and
                        indicators.get('rsi', 50) < 40):
                    return {
                        'position_id': position['id'],
                        'symbol': symbol,
                        'exit_price': current_price,
                        'profit_pct': profit_pct,
                        'reason': 'Technical indicators turned bearish'
                    }

        else:  # SHORT
            profit_pct = ((entry_price - current_price) / entry_price) * 100

            # Check stop loss
            if current_price >= stop_loss:
                return {
                    'position_id': position['id'],
                    'symbol': symbol,
                    'exit_price': current_price,
                    'profit_pct': profit_pct,
                    'reason': 'Stop loss triggered'
                }

            # Check take profit
            if current_price <= take_profit:
                return {
                    'position_id': position['id'],
                    'symbol': symbol,
                    'exit_price': current_price,
                    'profit_pct': profit_pct,
                    'reason': 'Take profit reached'
                }

            # Check technical indicators if provided
            if indicators:
                # Exit on strong bullish signals
                if (indicators.get('macd_diff', 0) > 0.0002 and
                        indicators.get('rsi', 50) > 60):
                    return {
                        'position_id': position['id'],
                        'symbol': symbol,
                        'exit_price': current_price,
                        'profit_pct': profit_pct,
                        'reason': 'Technical indicators turned bullish'
                    }

        return None

    def _update_ai_memory(self, symbol, direction, profit_pct):
        """Update AI memory with trade result"""
        if symbol not in self.ai_memory:
            self.ai_memory[symbol] = {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'total_profit': 0,
                'avg_pnl': 0,
                'win_rate': 0,
                'long_win_rate': 0,
                'short_win_rate': 0,
                'long_trades': 0,
                'short_trades': 0,
                'long_wins': 0,
                'short_wins': 0
            }

        # Update trade statistics
        memory = self.ai_memory[symbol]
        memory['total_trades'] += 1
        memory['total_profit'] += profit_pct

        if profit_pct > 0:
            memory['winning_trades'] += 1
        else:
            memory['losing_trades'] += 1

        if direction == 'LONG':
            memory['long_trades'] += 1
            if profit_pct > 0:
                memory['long_wins'] += 1
        else:  # SHORT
            memory['short_trades'] += 1
            if profit_pct > 0:
                memory['short_wins'] += 1

        # Calculate averages
        memory['avg_pnl'] = memory['total_profit'] / memory['total_trades']
        memory['win_rate'] = (memory['winning_trades'] / memory['total_trades']) * 100

        if memory['long_trades'] > 0:
            memory['long_win_rate'] = (memory['long_wins'] / memory['long_trades']) * 100

        if memory['short_trades'] > 0:
            memory['short_win_rate'] = (memory['short_wins'] / memory['short_trades']) * 100

        # Save updated memory
        self._save_ai_memory()

    def get_position_summary(self):
        """Get a summary of all active positions"""
        return self.active_positions

    def get_ai_memory_summary(self):
        """Get a summary of AI memory for all symbols"""
        return self.ai_memory

    def generate_weekly_report(self):
        """Generate a weekly performance report"""
        # Get closed positions from the past 7 days
        conn = sqlite3.connect(os.path.join(self.db_path, 'positions.db'))
        cursor = conn.cursor()

        one_week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute('''
        SELECT symbol, position_type, entry_price, exit_price, profit_loss_percent
        FROM positions
        WHERE status = 'CLOSED' AND exit_time > ?
        ''', (one_week_ago,))

        positions = cursor.fetchall()
        conn.close()

        if not positions:
            return "No closed positions in the past week."

        # Calculate statistics
        total_trades = len(positions)
        winning_trades = sum(1 for p in positions if p[4] > 0)
        losing_trades = total_trades - winning_trades

        win_rate = (winning_trades / total_trades) * 100 if total_trades > 0 else 0
        avg_profit = sum(p[4] for p in positions) / total_trades if total_trades > 0 else 0

        # Group by symbol
        symbol_stats = {}
        for p in positions:
            symbol = p[0]
            profit = p[4]

            if symbol not in symbol_stats:
                symbol_stats[symbol] = {
                    'trades': 0,
                    'wins': 0,
                    'total_profit': 0
                }

            symbol_stats[symbol]['trades'] += 1
            if profit > 0:
                symbol_stats[symbol]['wins'] += 1
            symbol_stats[symbol]['total_profit'] += profit

        # Format report
        report = f"📊 *Weekly Performance Report*\n\n"
        report += f"Period: {one_week_ago} to {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        report += f"Total Trades: {total_trades}\n"
        report += f"Win Rate: {win_rate:.2f}%\n"
        report += f"Average P/L: {avg_profit:.2f}%\n\n"

        # Top 5 performing symbols
        top_symbols = sorted(symbol_stats.items(), key=lambda x: x[1]['total_profit'], reverse=True)[:5]

        report += "*Top Performing Symbols:*\n"
        for symbol, stats in top_symbols:
            symbol_win_rate = (stats['wins'] / stats['trades']) * 100 if stats['trades'] > 0 else 0
            avg_symbol_profit = stats['total_profit'] / stats['trades'] if stats['trades'] > 0 else 0

            report += f"- {symbol}: {avg_symbol_profit:.2f}% avg ({symbol_win_rate:.1f}% win rate, {stats['trades']} trades)\n"

        return report

    def should_take_trade(self, symbol, direction):
        """Determine if a trade should be taken based on AI memory and market conditions"""
        # Check if symbol is in excluded list
        if symbol in EXCLUDED_SYMBOLS:
            logger.info(f"Skipping {symbol} as it's in the excluded list")
            return False

        # Check if we already have a position for this symbol
        if symbol in self.active_positions:
            logger.info(f"Skipping {symbol} as we already have an active position")
            return False

        # Check AI memory for this symbol
        if symbol in self.ai_memory:
            memory = self.ai_memory[symbol]

            # Skip if win rate is too low with sufficient sample size
            if memory['total_trades'] >= 5 and memory['win_rate'] < 40:
                logger.info(f"Skipping {symbol} due to low win rate: {memory['win_rate']:.2f}%")
                return False

            # Check direction-specific win rates
            if direction == 'LONG' and memory['long_trades'] >= 3:
                if memory['long_win_rate'] < 40:
                    logger.info(f"Skipping {symbol} LONG due to low win rate: {memory['long_win_rate']:.2f}%")
                    return False

            if direction == 'SHORT' and memory['short_trades'] >= 3:
                if memory['short_win_rate'] < 40:
                    logger.info(f"Skipping {symbol} SHORT due to low win rate: {memory['short_win_rate']:.2f}%")
                    return False

        # Check maximum drawdown
        current_drawdown = self._calculate_current_drawdown()
        if current_drawdown > MAX_DRAWDOWN_PERCENTAGE * 100:
            logger.info(f"Skipping {symbol} due to excessive drawdown: {current_drawdown:.2f}%")
            return False

        # Check maximum open positions
        max_positions = 5  # Configurable
        if len(self.active_positions) >= max_positions:
            logger.info(f"Skipping {symbol} as maximum number of positions ({max_positions}) reached")
            return False

        return True

    def _calculate_current_drawdown(self):
        """Calculate current drawdown from open positions"""
        if not self.active_positions:
            return 0

        total_investment = 0
        current_value = 0

        for symbol, position in self.active_positions.items():
            entry_price = position['entry_price']
            direction = position['direction']

            # Get current price (this is a placeholder - you should implement proper price fetching)
            current_price = position.get('current_price', entry_price)

            # Calculate position size
            position_size = self.calculate_position_size(symbol, entry_price, direction)

            total_investment += position_size

            if direction == 'LONG':
                current_position_value = position_size * (current_price / entry_price)
            else:  # SHORT
                current_position_value = position_size * (2 - (current_price / entry_price))

            current_value += current_position_value

        # Calculate drawdown percentage
        if total_investment > 0:
            drawdown_pct = ((total_investment - current_value) / total_investment) * 100
            return max(0, drawdown_pct)

        return 0

    def calculate_position_size(self, symbol, entry_price, direction, stop_loss=None):
        """Calculate position size based on risk management rules"""
        # If stop loss is not provided, calculate it
        if stop_loss is None:
            if direction == 'LONG':
                stop_loss = entry_price * (1 - STOP_LOSS_PERCENTAGE)
            else:  # SHORT
                stop_loss = entry_price * (1 + STOP_LOSS_PERCENTAGE)

        # Calculate risk amount
        risk_amount = DEFAULT_ACCOUNT_BALANCE * RISK_PER_TRADE

        # Calculate position size
        if direction == 'LONG':
            risk_per_unit = entry_price - stop_loss
        else:  # SHORT
            risk_per_unit = stop_loss - entry_price

        # Avoid division by zero
        if risk_per_unit <= 0:
            logger.warning(f"Invalid risk per unit for {symbol}: {risk_per_unit}")
            return 0

        # Calculate units
        units = risk_amount / risk_per_unit

        # Calculate position size with leverage
        position_size = units * entry_price / DEFAULT_LEVERAGE

        return position_size
