# Environment Variables
import os
import dotenv

# Load environment variables
dotenv.load_dotenv()


API_PORT = os.getenv("API_PORT", 11300)
API_HOST = os.getenv("API_HOST", "localhost")

BROKER_URL = os.getenv("RABBIT_MQ_URI", "amqp://guest:guest@localhost:5672//")

TOKEN_EXPIRATION_DAYS = 7
SECRET_KEY = os.getenv("SECRET_KEY", "super_secret_key")
MASTER_KEY = os.getenv("MASTER_KEY", "master_key")
