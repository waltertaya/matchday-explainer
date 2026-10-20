from dotenv import load_dotenv
import os

load_dotenv()

DATA_DIR = os.getenv('DATA_DIR', './data')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
EMBEDDING_MODEL = os.getenv('EMBEDDING_MODEL', 'text-embedding-3-small')
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
ENVIRONMENT=os.getenv("ENVIRONMENT", "production")

os.makedirs(DATA_DIR, exist_ok=True)
