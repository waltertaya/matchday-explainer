from dotenv import load_dotenv
import os
from pathlib import Path

load_dotenv()

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = os.getenv('DATA_DIR', str(ROOT / 'data'))
IFAB_DIR = os.getenv('IFAB_DIR', str(ROOT / 'ifab'))
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
EMBEDDING_MODEL = os.getenv('EMBEDDING_MODEL', 'text-embedding-3-small')
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")

EMBEDDING_DIMENSIONS = int(os.getenv("EMBEDDING_DIMENSIONS", "1536"))
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(IFAB_DIR, exist_ok=True)
