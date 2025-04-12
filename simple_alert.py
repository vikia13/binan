import datetime

class SimpleAlert:
    def __init__(self):
        self.log_file = open("alerts.log", "a")
        print("Simple alert system started - alerts will be logged to 'alerts.log'")

    def send_message(self, message):
        """Log message to file and console"""
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {message}\n"

        # Print to console
        print(log_entry)

        # Write to log file
        self.log_file.write(log_entry)
        self.log_file.flush()

        return True

    def stop(self):
        """Close log file"""
        self.log_file.close()
