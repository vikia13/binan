import pandas as pd
from ta.momentum import RSIIndicator, StochasticOscillator
from ta.trend import MACD, ADXIndicator
from ta.volatility import BollingerBands
import datetime
from config import (
    TIME_INTERVAL_MINUTES,
    PRICE_CHANGE_THRESHOLD,
    RSI_PERIOD,
    MACD_FAST,
    MACD_SLOW,
    MACD_SIGNAL,
    BOLLINGER_PERIOD,
    BOLLINGER_STD,
    EMA_50_PERIOD,
    EMA_200_PERIOD,
    ADX_PERIOD,
    ADX_THRESHOLD,
    STOCH_RSI_PERIOD,
    STOCH_RSI_K,
    STOCH_RSI_D
)


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
        if symbol not in self.symbol_data or len(self.symbol_data[symbol]) < 30:
            return None

        # Convert to DataFrame
        df = pd.DataFrame(self.symbol_data[symbol])
        df = df.sort_values('timestamp')
        df = df.drop_duplicates(subset='timestamp')

        # Calculate indicators
        # RSI
        rsi_indicator = RSIIndicator(
            close=df['price'],
            window=RSI_PERIOD
        )
        df['rsi'] = rsi_indicator.rsi()

        # MACD
        macd_indicator = MACD(
            close=df['price'],
            window_fast=MACD_FAST,
            window_slow=MACD_SLOW,
            window_sign=MACD_SIGNAL
        )
        df['macd'] = macd_indicator.macd()
        df['macd_signal'] = macd_indicator.macd_signal()
        df['macd_diff'] = macd_indicator.macd_diff()

        # Bollinger Bands
        bollinger = BollingerBands(
            close=df['price'],
            window=BOLLINGER_PERIOD,
            window_dev=BOLLINGER_STD
        )
        df['bb_upper'] = bollinger.bollinger_hband()
        df['bb_middle'] = bollinger.bollinger_mavg()
        df['bb_lower'] = bollinger.bollinger_lband()

        # VWAP (simplified version - usually calculated from open of trading day)
        df['vwap'] = (df['price'] * df['volume']).cumsum() / df['volume'].cumsum()

        # Calculate short-term price changes
        df['price_pct_change'] = df['price'].pct_change(periods=TIME_INTERVAL_MINUTES) * 100

        # Add EMA 50 and 200
        df['ema_50'] = df['price'].ewm(span=EMA_50_PERIOD, adjust=False).mean()
        df['ema_200'] = df['price'].ewm(span=EMA_200_PERIOD, adjust=False).mean()

        # Add EMA crossover signal
        df['ema_crossover'] = 0
        df.loc[df['ema_50'] > df['ema_200'], 'ema_crossover'] = 1
        df.loc[df['ema_50'] < df['ema_200'], 'ema_crossover'] = -1

        # Add ADX indicator
        adx = ADXIndicator(
            high=df['price'],  # Using price as high/low/close since we don't have OHLC data
            low=df['price'],
            close=df['price'],
            window=ADX_PERIOD
        )
        df['adx'] = adx.adx()
        df['adx_pos'] = adx.adx_pos()
        df['adx_neg'] = adx.adx_neg()

        # Add Stochastic RSI
        stoch = StochasticOscillator(
            high=df['price'],
            low=df['price'],
            close=df['price'],
            window=STOCH_RSI_PERIOD,
            smooth_window=STOCH_RSI_K
        )
        df['stoch_k'] = stoch.stoch()
        df['stoch_d'] = stoch.stoch_signal()

        # Filter out NaN values
        df = df.dropna()

        return df

    def detect_trend(self, symbol):
        df = self.calculate_indicators(symbol)
        if df is None or len(df) < TIME_INTERVAL_MINUTES:
            return None

        current_time = int(datetime.datetime.now().timestamp() * 1000)
        last_processed_time = self.last_processed.get(symbol, 0)

        # Check if enough time has passed since last processing
        if current_time - last_processed_time < TIME_INTERVAL_MINUTES * 60 * 1000:
            return None

        # Get the latest data
        latest = df.iloc[-1]

        # Detect pump (long) signal with enhanced criteria
        pump_signal = False
        if (
                latest['price_pct_change'] > PRICE_CHANGE_THRESHOLD and
                latest['rsi'] > 50 and
                latest['macd_diff'] > 0 and
                latest['price'] > latest['vwap'] and
                latest['ema_crossover'] >= 0 and  # EMA50 >= EMA200
                latest['adx'] > ADX_THRESHOLD  # Strong trend
        ):
            pump_signal = True

        # Detect dump (short) signal with enhanced criteria
        dump_signal = False
        if (
                latest['price_pct_change'] < -PRICE_CHANGE_THRESHOLD and
                latest['rsi'] < 50 and
                latest['macd_diff'] < 0 and
                latest['price'] < latest['vwap'] and
                latest['ema_crossover'] <= 0 and  # EMA50 <= EMA200
                latest['adx'] > ADX_THRESHOLD  # Strong trend
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
                'adx': latest['adx'],
                'ema_crossover': latest['ema_crossover'],
                'stoch_k': latest['stoch_k'],
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
                'adx': latest['adx'],
                'ema_crossover': latest['ema_crossover'],
                'stoch_k': latest['stoch_k'],
                'timestamp': current_time
            }

        return None

    def detect_exit_signal(self, position):
        """
        Enhanced exit signal detection with improved criteria
        """
        symbol = position['symbol']
        trend = position['trend']
        entry_price = position['entry_price']

        # Add this block to prevent immediate exits
        if 'timestamp' in position:
            entry_time = position['timestamp']
            current_time = int(datetime.datetime.now().timestamp() * 1000)
            # Require minimum 15 minutes holding time
            if current_time - entry_time < 15 * 60 * 1000:
                return None

        df = self.calculate_indicators(symbol)
        if df is None or len(df) < 5:  # Need at least a few data points
            return None

        # Get the latest data
        latest = df.iloc[-1]
        current_price = latest['price']

        # Calculate profit/loss percentage
        if trend == 'LONG':
            profit_pct = ((current_price - entry_price) / entry_price) * 100

            # Exit conditions for LONG position with enhanced criteria
            if (
                    # Strong reversal signal
                    (latest['macd_diff'] < -0.0002 and latest['rsi'] < 40) or
                    # Overbought condition
                    (latest['rsi'] > 75 and latest['stoch_k'] > 80) or
                    # Price drops below VWAP significantly
                    (latest['price'] < latest['vwap'] * 0.99) or
                    # EMA crossover turns bearish
                    (latest['ema_crossover'] == -1 and latest['ema_crossover'].shift(1).iloc[0] == 1)
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

            # Exit conditions for SHORT position with enhanced criteria
            if (
                    # Strong reversal signal
                    (latest['macd_diff'] > 0.0002 and latest['rsi'] > 60) or
                    # Oversold condition
                    (latest['rsi'] < 25 and latest['stoch_k'] < 20) or
                    # Price rises above VWAP significantly
                    (latest['price'] > latest['vwap'] * 1.01) or
                    # EMA crossover turns bullish
                    (latest['ema_crossover'] == 1 and latest['ema_crossover'].shift(1).iloc[0] == -1)
            ):
                return {
                    'symbol': symbol,
                    'exit_price': current_price,
                    'profit_pct': profit_pct,
                    'reason': 'Trend reversal detected',
                    'timestamp': int(datetime.datetime.now().timestamp() * 1000)
                }

        return None

    def get_market_data(self, symbol, period=100):
        """
        Extract the most recent market data for AI model training
        """
        if symbol not in self.symbol_data or len(self.symbol_data[symbol]) < period:
            return None

        df = self.calculate_indicators(symbol)
        if df is None:
            return None

        # Get the most recent data points
        return df.tail(period)
