import os
import sys
import signal
import subprocess
import time
import logging
import psutil

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("cleanup.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("Cleanup")


def kill_existing_instances():
    """Kill any existing Python processes running the main.py script"""
    logger.info("Checking for existing instances...")

    # Get the current process ID
    current_pid = os.getpid()

    try:
        # Find and kill all Python processes running main.py
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                # Check if it's a Python process
                if proc.info['name'] and 'python' in proc.info['name'].lower():
                    cmdline = proc.info['cmdline']
                    if cmdline and any('main.py' in cmd for cmd in cmdline):
                        pid = proc.info['pid']
                        if pid != current_pid:
                            logger.info(f"Killing existing process with PID {pid}")
                            try:
                                # Try to terminate gracefully first
                                proc.terminate()
                                # Wait for it to terminate
                                gone, alive = psutil.wait_procs([proc], timeout=3)
                                if alive:
                                    # If still alive, kill it
                                    for p in alive:
                                        p.kill()
                            except:
                                logger.error(f"Failed to kill process {pid}")
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
    except Exception as e:
        logger.error(f"Error checking for existing processes: {e}")

    # Additional check for any processes using the Telegram API
    try:
        for proc in psutil.process_iter(['pid']):
            try:
                # Check if this process has network connections
                if hasattr(proc, 'connections'):
                    connections = proc.connections()
                    for conn in connections:
                        if conn.status == 'ESTABLISHED' and 'api.telegram.org' in str(conn):
                            pid = proc.pid
                            if pid != current_pid:
                                logger.info(f"Killing process with Telegram connection: {pid}")
                                try:
                                    proc.terminate()
                                    gone, alive = psutil.wait_procs([proc], timeout=3)
                                    if alive:
                                        for p in alive:
                                            p.kill()
                                except:
                                    logger.error(f"Failed to kill process {pid}")
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
    except Exception as e:
        logger.error(f"Error checking for Telegram connections: {e}")


if __name__ == "__main__":
    logger.info("Starting cleanup process...")

    # Kill any existing instances
    kill_existing_instances()

    # Wait for processes to fully terminate
    logger.info("Waiting for processes to terminate...")
    time.sleep(5)

    # Reset Telegram webhook
    logger.info("Resetting Telegram webhook...")
    os.system(f"{sys.executable} reset_telegram.py")

    # Wait for the reset to take effect
    logger.info("Waiting for Telegram reset to take effect...")
    time.sleep(10)

    # Run the main script
    logger.info("Starting main application...")
    os.system(f"{sys.executable} main.py")
