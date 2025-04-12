import os
import subprocess
import sys

def setup_environment():
    print("Setting up Binance AI Futures Screener (Simplified Version)...")

    # Create required directories
    os.makedirs("models", exist_ok=True)

    # Install minimal dependencies
    print("Installing required packages...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "websocket-client==1.5.1"])
    subprocess.check_call([sys.executable, "-m", "pip", "install", "python-telegram-bot==13.15"])
    subprocess.check_call([sys.executable, "-m", "pip", "install", "python-dotenv==1.0.0"])

    # Check if .env file exists
    if not os.path.exists(".env"):
        print("Creating .env file template...")
        with open(".env", "w") as f:
            f.write("TELEGRAM_TOKEN=your_telegram_bot_token\n")
            f.write("TELEGRAM_CHAT_ID=your_telegram_chat_id\n")
        print("\nIMPORTANT: Please edit the .env file with your Telegram bot token and chat ID")

    print("\nSetup complete! You can now run the system with: python main.py")

if __name__ == "__main__":
    setup_environment()
