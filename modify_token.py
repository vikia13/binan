import os
from dotenv import load_dotenv, set_key
import random
import string

# Load environment variables
load_dotenv()
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")

if TELEGRAM_TOKEN:
    # Add a random suffix to the token to create a new session


    # Generate a random 4-character suffix
    suffix = ''.join(random.choices(string.ascii_lowercase, k=4))

    # Split the token at the colon
    parts = TELEGRAM_TOKEN.split(':')
    if len(parts) == 2:
        # Add the suffix to the second part
        new_token = f"{parts[0]}:{suffix}{parts[1]}"

        # Update the .env file
        env_path = os.path.join(os.getcwd(), '.env')
        set_key(env_path, "TELEGRAM_TOKEN", new_token)

        print(f"Updated Telegram token with random suffix: {suffix}")
    else:
        print("Token format not recognized")
else:
    print("No Telegram token found in environment variables")
