from dotenv import load_dotenv
import os

load_dotenv()

DATA_DIR = os.getenv('DATA_DIR', './data')
IFAB_DIR = os.getenv('IFAB_DIR', './ifab')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
EMBEDDING_MODEL = os.getenv('EMBEDDING_MODEL', 'text-embedding-3-small')
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")

EMBEDDING_DIMENSIONS = int(os.getenv("EMBEDDING_DIMENSIONS", "1536"))
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(IFAB_DIR, exist_ok=True)
