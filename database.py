import sqlite3
import datetime
import threading


class Database:
    def __init__(self, db_path="positions.db"):
        self.db_path = db_path
        self.connection = None
        self.cursor = None
        self.lock = threading.RLock()  # Add thread lock
        self.init_db()

    def init_db(self):
        try:
            # Use check_same_thread=False to allow cross-thread access
            self.connection = sqlite3.connect(self.db_path, check_same_thread=False)
            self.cursor = self.connection.cursor()

            # Create tables if they don't exist
            self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                entry_price REAL NOT NULL,
                trend TEXT NOT NULL,
                entry_time TEXT NOT NULL,
                exit_price REAL,
                exit_time TEXT,
                signal_id INTEGER,
                status TEXT DEFAULT 'OPEN'
            )
            ''')

            self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS signal_counts (
                symbol TEXT PRIMARY KEY,
                count INTEGER DEFAULT 0,
                date TEXT NOT NULL,
                max_count INTEGER DEFAULT 3
            )
            ''')

            self.connection.commit()
        except Exception as e:
            print(f"Database initialization error: {e}")

    def add_position(self, symbol, entry_price, trend, signal_id=None):
        with self.lock:  # Use lock for thread safety
            try:
                entry_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self.cursor.execute(
                    "INSERT INTO positions (symbol, entry_price, trend, entry_time, signal_id, status) VALUES (?, ?, ?, ?, ?, ?)",
                    (symbol, entry_price, trend, entry_time, signal_id, 'OPEN')
                )
                self.connection.commit()
                return self.cursor.lastrowid
            except Exception as e:
                print(f"Error adding position: {e}")
                return None

    def close_position(self, position_id, exit_price):
        with self.lock:  # Use lock for thread safety
            try:
                exit_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self.cursor.execute(
                    "UPDATE positions SET exit_price = ?, exit_time = ?, status = 'CLOSED' WHERE id = ?",
                    (exit_price, exit_time, position_id)
                )
                self.connection.commit()
                return True
            except Exception as e:
                print(f"Error closing position: {e}")
                return False

    def get_open_positions(self):
        with self.lock:  # Use lock for thread safety
            try:
                self.cursor.execute("SELECT * FROM positions WHERE status = 'OPEN'")
                return self.cursor.fetchall()
            except Exception as e:
                print(f"Error getting open positions: {e}")
                return []

    def get_position_by_signal_id(self, signal_id):
        with self.lock:  # Use lock for thread safety
            try:
                self.cursor.execute("SELECT * FROM positions WHERE signal_id = ? AND status = 'OPEN'", (signal_id,))
                return self.cursor.fetchone()
            except Exception as e:
                print(f"Error getting position by signal ID: {e}")
                return None

    def increment_signal_count(self, symbol):
        with self.lock:  # Use lock for thread safety
            try:
                today = datetime.datetime.now().strftime("%Y-%m-%d")

                # Check if entry exists for today
                self.cursor.execute("SELECT count, max_count FROM signal_counts WHERE symbol = ? AND date = ?",
                                    (symbol, today))
                result = self.cursor.fetchone()

                if result:
                    # Update existing entry
                    current_count = result[0]
                    max_count = result[1] or 3  # Default to 3 if None

                    # Only increment if below max count
                    if current_count < max_count:
                        new_count = current_count + 1
                        self.cursor.execute(
                            "UPDATE signal_counts SET count = ? WHERE symbol = ? AND date = ?",
                            (new_count, symbol, today)
                        )
                        self.connection.commit()
                        return True
                    else:
                        # Already at max count
                        return False
                else:
                    # Create new entry with default max_count of 3
                    self.cursor.execute(
                        "INSERT INTO signal_counts (symbol, count, date, max_count) VALUES (?, ?, ?, ?)",
                        (symbol, 1, today, 3)
                    )
                    self.connection.commit()
                    return True
            except Exception as e:
                print(f"Error incrementing signal count: {e}")
                # Try to handle the unique constraint error gracefully
                if "UNIQUE constraint failed" in str(e):
                    try:
                        # Try again with an update instead
                        self.cursor.execute(
                            "UPDATE signal_counts SET count = count + 1 WHERE symbol = ? AND date = ?",
                            (symbol, today)
                        )
                        self.connection.commit()
                        return True
                    except Exception as e2:
                        print(f"Error in fallback update: {e2}")
                return False

    def get_signal_count(self, symbol):
        with self.lock:  # Use lock for thread safety
            try:
                today = datetime.datetime.now().strftime("%Y-%m-%d")
                self.cursor.execute("SELECT count FROM signal_counts WHERE symbol = ? AND date = ?", (symbol, today))
                result = self.cursor.fetchone()
                return result[0] if result else 0
            except Exception as e:
                print(f"Error getting signal count: {e}")
                return 0

    def set_max_signals(self, symbol, max_count):
        with self.lock:  # Use lock for thread safety
            try:
                today = datetime.datetime.now().strftime("%Y-%m-%d")

                # Check if entry exists for today
                self.cursor.execute("SELECT count FROM signal_counts WHERE symbol = ? AND date = ?", (symbol, today))
                result = self.cursor.fetchone()

                if result:
                    # Update existing entry
                    self.cursor.execute(
                        "UPDATE signal_counts SET max_count = ? WHERE symbol = ? AND date = ?",
                        (max_count, symbol, today)
                    )
                else:
                    # Create new entry
                    self.cursor.execute(
                        "INSERT INTO signal_counts (symbol, count, date, max_count) VALUES (?, ?, ?, ?)",
                        (symbol, 0, today, max_count)
                    )

                self.connection.commit()
                return True
            except Exception as e:
                print(f"Error setting max signals: {e}")
                return False

    def close(self):
        try:
            if self.connection:
                self.connection.close()
        except Exception as e:
            print(f"Error closing database: {e}")
