import json
import threading
import time
import logging
from websocket import create_connection
import websocket  # Import the module

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("websocket.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("WebSocketClient")


class WebSocketClient:
    def __init__(self, url, message_handler, reconnect_interval=5):
        self.url = url
        self.message_handler = message_handler
        self.reconnect_interval = reconnect_interval
        self.ws = None
        self.running = True
        self.thread = None

        # Start WebSocket connection in a separate thread
        self.thread = threading.Thread(target=self._run_forever)
        self.thread.daemon = True
        self.thread.start()

    def _on_message(self, ws, message):
        """Handle incoming WebSocket messages"""
        try:
            data = json.loads(message)
            self.message_handler(data)
        except Exception as e:
            logger.error(f"Error processing WebSocket message: {e}")

    def _on_error(self, ws, error):
        """Handle WebSocket errors"""
        logger.error(f"WebSocket error: {error}")

    def _on_close(self, ws, close_status_code, close_msg):
        """Handle WebSocket connection close"""
        logger.info(f"WebSocket connection closed: {close_status_code} - {close_msg}")

    def _on_open(self, ws):
        """Handle WebSocket connection open"""
        logger.info("WebSocket connection established")

    def _run_forever(self):
        """Maintain the WebSocket connection with automatic reconnection"""
        while self.running:
            try:
                logger.info(f"Connecting to WebSocket: {self.url}")
                # Use websocket.WebSocketApp instead of WebSocketApp
                self.ws = websocket.WebSocketApp(
                    self.url,
                    on_message=self._on_message,
                    on_error=self._on_error,
                    on_close=self._on_close,
                    on_open=self._on_open
                )
                self.ws.run_forever()

                # If we get here, the connection was closed
                if not self.running:
                    break

                logger.info(f"WebSocket disconnected. Reconnecting in {self.reconnect_interval} seconds...")
                time.sleep(self.reconnect_interval)

            except Exception as e:
                logger.error(f"Error in WebSocket connection: {e}")
                time.sleep(self.reconnect_interval)

    def close(self):
        """Close the WebSocket connection"""
        logger.info("Closing WebSocket connection...")
        self.running = False

        if self.ws:
            try:
                self.ws.close()
            except:
                pass

        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2)
