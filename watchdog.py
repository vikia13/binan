#!/usr/bin/env python3
import subprocess
import time
import sys
import os
import logging
from datetime import datetime

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("watchdog.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("Watchdog")

def run_with_watchdog(script_path, max_restarts=10, restart_delay=10):
    """Run a Python script with watchdog protection"""
    restarts = 0

    while restarts < max_restarts:
        start_time = datetime.now()
        logger.info(f"Starting script: {script_path} (Attempt {restarts+1}/{max_restarts})")

        try:
            # Run the script as a subprocess
            process = subprocess.Popen([sys.executable, script_path])
            return_code = process.wait()

            # Check if process exited normally
            if return_code == 0:
                logger.info("Script exited normally. Watchdog terminating.")
                break

            # Calculate runtime
            runtime = datetime.now() - start_time
            runtime_minutes = runtime.total_seconds() / 60

            # If the script ran for more than 30 minutes, reset the restart counter
            if runtime_minutes > 30:
                logger.info(f"Script ran for {runtime_minutes:.1f} minutes before exiting. Resetting restart counter.")
                restarts = 0
            else:
                restarts += 1

            logger.warning(f"Script exited with code {return_code}. Restarting in {restart_delay} seconds...")
            time.sleep(restart_delay)

        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received. Terminating watchdog.")
            if process and process.poll() is None:
                process.terminate()
            break

        except Exception as e:
            logger.error(f"Error in watchdog: {e}")
            restarts += 1
            time.sleep(restart_delay)

    if restarts >= max_restarts:
        logger.error(f"Maximum restart attempts ({max_restarts}) reached. Giving up.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python watchdog.py <script_path>")
        sys.exit(1)

    script_path = sys.argv[1]
    if not os.path.exists(script_path):
        print(f"Error: Script '{script_path}' not found.")
        sys.exit(1)

    run_with_watchdog(script_path)
