import datetime
import time
from config import TIME_INTERVAL_MINUTES, PRICE_CHANGE_THRESHOLD

class DataProcessor:
    def __init__(self):
        self.symbol_data = {}
        self.last_processed = {}

    def update_data(self, ticker_data):
        symbol = ticker_data['symbol']

        if symbol not in self.symbol_data:
            self.symbol_data[symbol] = []
            self.last_processed[symbol] = 0

        # Add new data point
        self.symbol_data[symbol].append(ticker_data)

        # Keep only recent data (last 3 hours)
        current_time = int(datetime.datetime.now().timestamp() * 1000)
        three_hours_ago = current_time - (3 * 60 * 60 * 1000)
        self.symbol_data[symbol] = [
            d for d in self.symbol_data[symbol]
            if d['timestamp'] > three_hours_ago
        ]

    def calculate_indicators(self, symbol):
        """Calculate basic indicators without pandas/numpy"""
        if symbol not in self.symbol_data or len(self.symbol_data[symbol]) < 30:
            return None

        data = sorted(self.symbol_data[symbol], key=lambda x: x['timestamp'])

        # Simple implementation of indicators
        prices = [item['price'] for item in data]
        volumes = [item['volume'] for item in data]
        timestamps = [item['timestamp'] for item in data]

        # Calculate price changes
        price_changes = []
        for i in range(1, len(prices)):
            pct_change = ((prices[i] - prices[i-1]) / prices[i-1]) * 100
            price_changes.append(pct_change)

        # Simple RSI (14-period)
        rsi = self._calculate_simple_rsi(prices, 14)

        # Simple MACD
        macd, signal = self._calculate_simple_macd(prices)

        # Return data with indicators
        result = []
        for i in range(len(data)):
            item = data[i].copy()
            if i > 0:
                item['price_pct_change'] = price_changes[i-1]
            else:
                item['price_pct_change'] = 0

            if i < len(rsi):
                item['rsi'] = rsi[i]
            else:
                item['rsi'] = 50  # Default neutral value

            if i < len(macd):
                item['macd'] = macd[i]
                item['macd_signal'] = signal[i]
                item['macd_diff'] = macd[i] - signal[i]
            else:
                item['macd'] = 0
                item['macd_signal'] = 0
                item['macd_diff'] = 0

            result.append(item)

        return result

    def _calculate_simple_rsi(self, prices, period=14):
        """Simple RSI implementation without numpy"""
        if len(prices) <= period:
            return [50] * len(prices)  # Default neutral value

        rsi_values = [50] * period  # First values default to neutral

        for i in range(period, len(prices)):
            gains = 0
            losses = 0

            # Calculate average gains and losses
            for j in range(i - period, i):
                change = prices[j+1] - prices[j]
                if change > 0:
                    gains += change
                else:
                    losses += abs(change)

            avg_gain = gains / period
            avg_loss = losses / period

            if avg_loss == 0:
                rsi = 100
            else:
                rs = avg_gain / avg_loss
                rsi = 100 - (100 / (1 + rs))

            rsi_values.append(rsi)

        return rsi_values

    def _calculate_simple_macd(self, prices, fast=12, slow=26, signal=9):
        """Simple MACD implementation without numpy"""
        if len(prices) <= slow:
            return [0] * len(prices), [0] * len(prices)

        # Calculate EMAs
        ema_fast = self._calculate_ema(prices, fast)
        ema_slow = self._calculate_ema(prices, slow)

        # Calculate MACD line
        macd_line = [0] * slow
        for i in range(slow, len(prices)):
            macd_line.append(ema_fast[i] - ema_slow[i])

        # Calculate signal line
        signal_line = [0] * (slow + signal - 1)
        signal_line.extend(self._calculate_ema(macd_line[slow:], signal))

        return macd_line, signal_line

    def _calculate_ema(self, data, period):
        """Calculate Exponential Moving Average"""
        if len(data) <= period:
            return data

        ema = [sum(data[:period]) / period]  # First value is SMA
        multiplier = 2 / (period + 1)

        for i in range(period, len(data)):
            ema_value = (data[i] * multiplier) + (ema[-1] * (1 - multiplier))
            ema.append(ema_value)

        # Pad with zeros to maintain original length
        return [0] * (period - 1) + ema

    def detect_trend(self, symbol):
        """Detect trend based on simplified indicators"""
        result = self.calculate_indicators(symbol)
        if not result or len(result) < 5:
            return None

        current_time = int(datetime.datetime.now().timestamp() * 1000)
        last_processed_time = self.last_processed.get(symbol, 0)

        # Check if enough time has passed since last processing
        if current_time - last_processed_time < TIME_INTERVAL_MINUTES * 60 * 1000:
            return None

        # Get the latest data
        latest = result[-1]

        # Detect pump (long) signal
        pump_signal = False
        if (
            latest['price_pct_change'] > PRICE_CHANGE_THRESHOLD and
            latest['rsi'] > 50 and
            latest['macd_diff'] > 0
        ):
            pump_signal = True

        # Detect dump (short) signal
        dump_signal = False
        if (
            latest['price_pct_change'] < -PRICE_CHANGE_THRESHOLD and
            latest['rsi'] < 50 and
            latest['macd_diff'] < 0
        ):
            dump_signal = True

        # Update last processed time
        self.last_processed[symbol] = current_time

        if pump_signal:
            return {
                'symbol': symbol,
                'trend': 'LONG',
                'price': latest['price'],
                'price_change': latest['price_pct_change'],
                'rsi': latest['rsi'],
                'macd_diff': latest['macd_diff'],
                'timestamp': current_time
            }
        elif dump_signal:
            return {
                'symbol': symbol,
                'trend': 'SHORT',
                'price': latest['price'],
                'price_change': latest['price_pct_change'],
                'rsi': latest['rsi'],
                'macd_diff': latest['macd_diff'],
                'timestamp': current_time
            }

        return None

    def detect_exit_signal(self, position):
        """Detect exit signal based on simplified indicators"""
        symbol = position['symbol']
        trend = position['trend']
        entry_price = position['entry_price']

        result = self.calculate_indicators(symbol)
        if not result or len(result) < 5:
            return None

        # Get the latest data
        latest = result[-1]
        current_price = latest['price']

        # Calculate profit/loss percentage
        if trend == 'LONG':
            profit_pct = ((current_price - entry_price) / entry_price) * 100

            # Exit conditions for LONG position
            if (
                latest['macd_diff'] < 0 or  # MACD turning bearish
                latest['rsi'] > 70  # Overbought
            ):
                return {
                    'symbol': symbol,
                    'exit_price': current_price,
                    'profit_pct': profit_pct,
                    'reason': 'Trend reversal detected',
                    'timestamp': int(datetime.datetime.now().timestamp() * 1000)
                }

        elif trend == 'SHORT':
            profit_pct = ((entry_price - current_price) / entry_price) * 100

            # Exit conditions for SHORT position
            if (
                latest['macd_diff'] > 0 or  # MACD turning bullish
                latest['rsi'] < 30  # Oversold
            ):
                return {
                    'symbol': symbol,
                    'exit_price': current_price,
                    'profit_pct': profit_pct,
                    'reason': 'Trend reversal detected',
                    'timestamp': int(datetime.datetime.now().timestamp() * 1000)
                }

        return None