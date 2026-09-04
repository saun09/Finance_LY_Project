import os
from dotenv import load_dotenv

load_dotenv()

print(os.getenv("N8N_WEBHOOK_URL"))